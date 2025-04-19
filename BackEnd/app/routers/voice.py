# backend/app/routers/voice.py
import logging
import asyncio
import re # 정규식 임포트 (현재 로직에서는 필수는 아니지만 향후 사용을 위해)
from fastapi import APIRouter, WebSocket, WebSocketDisconnect
from starlette.websockets import WebSocketState
from app.services.stt_service import handle_stt_stream, STTTimeoutError
from app.services.llm_service import stream_llm_response
from app.services.tts_service import synthesize_speech_stream # 업데이트된 TTS 서비스 임포트
from google.api_core import exceptions as google_exceptions
from typing import Set, AsyncIterator # AsyncIterator 임포트
import os # 오류 확인을 위한 임포트

# 로거 설정
logger = logging.getLogger(__name__)

# APIRouter 인스턴스
router = APIRouter(
    prefix="/ws",
    tags=["voice"],
)

# --- 텍스트 청킹을 위한 헬퍼 함수 ---
async def chunk_text_by_punctuation(
    llm_stream: AsyncIterator[str],
    min_length: int = 10, # 최소 길이를 약간 증가
    punctuation: str = '.?!,' # 구두점으로 분할
) -> AsyncIterator[str]:
    """
    LLM 텍스트 스트림을 비동기적으로 소비하고, 텍스트를 누적하여
    구두점이나 최소 길이로 분할된 청크를 생성하여 더 자연스러운 TTS 입력을 제공합니다.

    Args:
        llm_stream: LLM에서 텍스트 청크를 생성하는 비동기 이터레이터
        min_length: 구두점이 없을 때 생성하기 전에 누적할 대략적인 최소 길이
        punctuation: 문장을 분할할 구두점 문자들을 포함하는 문자열

    Yields:
        str: TTS에 적합한 처리된 텍스트 청크
    """
    temp_chunk = ""
    logger.debug("텍스트 청커 시작.")
    try:
        async for chunk_text in llm_stream:
            if not chunk_text: continue # LLM의 빈 청크 건너뛰기

            temp_chunk += chunk_text
            # print(f"누적된 텍스트: '{temp_chunk}'") # 디버그 로깅

            # 누적된 청크가 분할할 수 있을 만큼 충분히 긴지 확인
            if len(temp_chunk) >= min_length:
                last_punctuation_pos = -1
                # 마지막 구두점의 위치 찾기
                for i, char in enumerate(reversed(temp_chunk)):
                    if char in punctuation:
                        # 문자열 시작부터의 인덱스 계산
                        last_punctuation_pos = len(temp_chunk) - 1 - i
                        break # 마지막 것을 찾았으므로 중단

                if last_punctuation_pos != -1:
                    # 구두점을 찾았으므로, 그것까지의 부분을 생성
                    text_to_yield = temp_chunk[:last_punctuation_pos + 1].strip()
                    if text_to_yield:
                        logger.debug(f"텍스트 청커 생성 (구두점): '{text_to_yield}'")
                        yield text_to_yield
                    # 나머지는 다음 반복을 위해 보관
                    temp_chunk = temp_chunk[last_punctuation_pos + 1:]
                    # print(f"나머지: '{temp_chunk}'") # 디버그 로깅
                else:
                    # 구두점을 찾지 못했지만 길이는 충분함
                    # 전체 청크를 생성하고 초기화
                    # LLM이 구두점을 사용하지 않는 경우 매우 긴 청크가 되는 것을 방지
                    # 대안: 더 오래 기다릴 수 있지만 지연이 증가할 수 있음
                    text_to_yield = temp_chunk.strip()
                    if text_to_yield:
                        logger.debug(f"텍스트 청커 생성 (길이): '{text_to_yield}'")
                        yield text_to_yield
                    temp_chunk = ""

        # 스트림이 끝난 후 남은 텍스트 생성
        if temp_chunk and temp_chunk.strip():
            logger.debug(f"텍스트 청커 생성 (나머지): '{temp_chunk.strip()}'")
            yield temp_chunk.strip()

        logger.debug("텍스트 청커 종료.")

    except asyncio.CancelledError:
         logger.info("텍스트 청커 태스크 취소됨.")
         raise
    except Exception as e:
         logger.error(f"텍스트 청커에서 오류 발생: {e}", exc_info=True)
         # 오류 발생 전에 남은 청크를 생성 시도
         if temp_chunk and temp_chunk.strip():
              try: yield temp_chunk.strip()
              except Exception: pass
         raise # 오류를 다시 발생시킴


@router.websocket("/audio")
async def websocket_endpoint(websocket: WebSocket):
    """
    WebSocket 연결을 처리하고, 오디오 수신 -> STT -> LLM -> 텍스트 청킹 -> TTS -> 오디오 전송 파이프라인을 관리합니다.
    """
    await websocket.accept()
    client_host = websocket.client.host
    client_port = websocket.client.port
    client_info = f"{client_host}:{client_port}"
    logger.info(f"WebSocket 연결 수락됨: {client_info}")

    audio_queue = asyncio.Queue() # STT 입력 오디오 큐
    stt_task: asyncio.Task | None = None # STT 처리 태스크
    llm_tts_tasks: Set[asyncio.Task] = set() # LLM/TTS 처리 태스크 집합

    # 연결 상태 플래그 - 외부 스코프에서 정의
    is_connected = True

    # --- LLM, 텍스트 청킹, TTS 처리 함수 ---
    async def handle_llm_and_tts(transcript: str, ws: WebSocket, client_id: str):
        """LLM 응답을 받아 자연스럽게 청킹하고, TTS로 변환하여 WebSocket으로 오디오 청크를 전송합니다."""
        nonlocal is_connected
        logger.info(f"[{client_id}] 최종 STT 결과로 LLM->청커->TTS 파이프라인 시작: '{transcript[:50]}...'")
        llm_stream = None
        processed_text_stream = None
        tts_stream = None
        try:
            # 1. LLM 서비스 호출하여 텍스트 스트림 받기
            llm_stream = stream_llm_response(transcript, client_id)

            # 2. 텍스트 청킹 로직 적용
            processed_text_stream = chunk_text_by_punctuation(llm_stream)

            # 3. 처리된 텍스트 스트림으로 TTS 서비스 호출
            tts_stream = synthesize_speech_stream(processed_text_stream) # 청킹된 이터레이터 전달

            # 4. 오디오 청크를 WebSocket으로 스트리밍
            async for audio_chunk in tts_stream:
                if not is_connected:
                    logger.warning(f"[{client_id}] WebSocket 연결이 끊어져 TTS 오디오 전송 중단.")
                    break

                try:
                    if ws.client_state == WebSocketState.CONNECTED:
                        await ws.send_bytes(audio_chunk)
                        logger.debug(f"[{client_id}] TTS 오디오 청크 전송됨 ({len(audio_chunk)} bytes)")
                    else:
                         logger.warning(f"[{client_id}] WebSocket이 더 이상 연결되지 않았습니다. TTS 오디오 청크를 전송할 수 없습니다.")
                         is_connected = False
                         break
                except WebSocketDisconnect:
                    logger.warning(f"[{client_id}] TTS 오디오 청크 전송 중 WebSocket 연결이 끊어졌습니다.")
                    is_connected = False
                    break
                except Exception as e:
                    logger.warning(f"[{client_id}] TTS 오디오 청크 전송 중 오류: {e}")
                    if isinstance(e, (ConnectionResetError, BrokenPipeError)):
                         is_connected = False
                    break

            if is_connected:
                 logger.info(f"[{client_id}] LLM->청커->TTS 오디오 스트리밍 완료.")
            else:
                 logger.warning(f"[{client_id}] 연결 끊김으로 인해 LLM->청커->TTS 오디오 스트리밍이 중단되었습니다.")


        except asyncio.CancelledError:
            logger.info(f"[{client_id}] LLM->청커->TTS 파이프라인 태스크 취소됨.")
        except Exception as e:
            logger.error(f"[{client_id}] LLM->청커->TTS 파이프라인 처리 중 오류 발생: {e}", exc_info=True)
            if is_connected and ws.client_state == WebSocketState.CONNECTED:
                try:
                    error_message = f"응답 처리 중 서버 오류: {type(e).__name__}"
                    await ws.send_text(f'{{"error": "{error_message}"}}')
                except Exception as send_err:
                     logger.warning(f"[{client_id}] 클라이언트에게 오류 메시지 전송 실패: {send_err}")
        finally:
             logger.debug(f"[{client_id}] LLM->청커->TTS 파이프라인 태스크 실행 완료.")


    # --- STT 결과 처리 콜백 ---
    async def process_stt_result(transcript: str, is_final: bool):
        """STT 결과를 처리하는 콜백 함수. 최종 결과에서 LLM->청커->TTS 파이프라인을 시작합니다."""
        nonlocal llm_tts_tasks
        if not is_connected:
            logger.warning(f"[{client_info}] STT 결과가 수신되었지만 WebSocket이 연결되지 않았습니다. 무시합니다.")
            return

        if not is_final:
            logger.debug(f"[{client_info}] 중간 STT 결과: {transcript}")
            # 선택적으로 중간 결과 전송 (JSON 텍스트)
            # try:
            #     if websocket.client_state == WebSocketState.CONNECTED:
            #         await websocket.send_text(f'{{"transcript": "{transcript}", "is_final": false}}')
            # except Exception: pass
        else:
            logger.info(f"[{client_info}] 최종 STT 결과: {transcript}")
            # 선택적으로 최종 텍스트 결과 전송
            # try:
            #     if websocket.client_state == WebSocketState.CONNECTED:
            #          await websocket.send_text(f'{{"transcript": "{transcript}", "is_final": true}}')
            # except Exception: pass

            if transcript and transcript.strip():
                # LLM->청커->TTS 파이프라인을 별도 태스크로 시작
                llm_tts_task = asyncio.create_task(
                    handle_llm_and_tts(transcript, websocket, client_info)
                )
                llm_tts_tasks.add(llm_tts_task)
                llm_tts_task.add_done_callback(llm_tts_tasks.discard)
                logger.debug(f"[{client_info}] LLM->청커->TTS 파이프라인 태스크 생성됨: {llm_tts_task.get_name()}")
            else:
                logger.info(f"[{client_info}] 빈 최종 STT 결과. LLM->청커->TTS 파이프라인 건너뜀.")


    # --- 메인 루프: STT 관리 및 메시지 수신 ---
    try:
        while is_connected:
            # 1. STT 태스크 관리 (시작 또는 재시작)
            if stt_task is None or stt_task.done():
                should_restart_stt = False
                if stt_task and stt_task.done():
                    try:
                        stt_task.result()
                    except STTTimeoutError:
                        logger.info(f"[{client_info}] STT 타임아웃 감지. STT 서비스를 재시작합니다.")
                        should_restart_stt = True
                    except google_exceptions.InternalServerError as e_internal:
                         logger.warning(f"[{client_info}] STT 서비스 내부 서버 오류(500): {e_internal}. 재시작 시도.")
                         should_restart_stt = True
                    except asyncio.CancelledError:
                        logger.info(f"[{client_info}] 이전 STT 태스크가 취소되었습니다.")
                        if is_connected: should_restart_stt = True
                    except Exception as e:
                        logger.error(f"[{client_info}] 이전 STT 태스크에서 처리되지 않은 예외 발생: {e}. 연결 종료.", exc_info=True)
                        is_connected = False

                if is_connected and (stt_task is None or should_restart_stt):
                    logger.info(f"[{client_info}] STT 서비스 태스크 (재)시작 중...")
                    while not audio_queue.empty():
                        try:
                            audio_queue.get_nowait()
                            audio_queue.task_done()
                        except (asyncio.QueueEmpty, ValueError): break
                    logger.debug(f"[{client_info}] STT 재시작 전 오디오 큐 비움.")

                    stt_task = asyncio.create_task(
                        handle_stt_stream(audio_queue, process_stt_result)
                    )
                    await asyncio.sleep(0.1)

            # 2. WebSocket 메시지 수신 또는 STT 태스크 완료 대기
            if not is_connected: break

            tasks_to_wait = [asyncio.create_task(websocket.receive())]
            if stt_task and not stt_task.done():
                tasks_to_wait.append(stt_task)

            done, pending = await asyncio.wait(
                tasks_to_wait,
                return_when=asyncio.FIRST_COMPLETED
            )

            for task in done:
                if task == stt_task:
                     logger.debug(f"[{client_info}] STT 태스크 실행 완료 (대기 중 감지).")
                     try: task.result()
                     except STTTimeoutError: logger.info(f"[{client_info}] STT 타임아웃 감지 (대기 중).")
                     except google_exceptions.InternalServerError as e_internal: logger.warning(f"[{client_info}] STT 내부 서버 오류(500) 감지 (대기 중): {e_internal}.")
                     except asyncio.CancelledError: logger.info(f"[{client_info}] STT 태스크 취소됨 (대기 중).")
                     except Exception as e:
                          logger.error(f"[{client_info}] 처리되지 않은 STT 예외 (대기 중): {e}. 연결 종료.", exc_info=True)
                          is_connected = False
                     continue

                receive_task = task
                try:
                    data = receive_task.result()
                    if isinstance(data, dict):
                        if data.get("type") == "websocket.disconnect":
                            logger.warning(f"[{client_info}] WebSocket 연결 끊김 메시지 수신: {data}. 종료.")
                            is_connected = False
                        elif "text" in data:
                            text_data = data["text"]
                            logger.info(f"[{client_info}] 텍스트 메시지 수신: {text_data}")
                            if text_data.lower() in ["client stopped recording", "disconnect", "stop"]:
                                logger.info(f"[{client_info}] 클라이언트 중지 신호 수신. 오디오 큐에 None 전송.")
                                if audio_queue:
                                    try: await asyncio.wait_for(audio_queue.put(None), timeout=1.0)
                                    except asyncio.TimeoutError: logger.warning(f"[{client_info}] 오디오 큐에 None 전송 타임아웃.")
                        elif "bytes" in data:
                            audio_chunk = data["bytes"]
                            if audio_chunk and audio_queue: await audio_queue.put(audio_chunk)
                            else: logger.debug(f"[{client_info}] 빈 오디오 청크 수신, 무시됨.")
                    else:
                        logger.warning(f"[{client_info}] 예상치 못한 데이터 유형 수신: {type(data)}")

                except WebSocketDisconnect as e:
                    logger.warning(f"[{client_info}] 수신 중 WebSocket 연결 끊김: 코드 {e.code}, 이유: {e.reason}.")
                    is_connected = False
                except asyncio.CancelledError:
                     logger.info(f"[{client_info}] 수신 태스크 취소됨.")
                     is_connected = False
                except Exception as e_recv:
                    logger.error(f"[{client_info}] WebSocket 수신 중 오류: {e_recv}", exc_info=True)
                    is_connected = False

            for task in pending:
                 if task != stt_task: task.cancel()


    except WebSocketDisconnect as e:
        logger.warning(f"WebSocket 연결이 외부에서 닫힘: {client_info} - 코드: {e.code}, 이유: {e.reason}")
        is_connected = False
    except asyncio.CancelledError:
        logger.info(f"[{client_info}] 메인 WebSocket 핸들러 태스크 취소됨.")
        is_connected = False
    except Exception as e:
        logger.error(f"WebSocket 핸들러에서 처리되지 않은 예외 발생 ({client_info}): {e}", exc_info=True)
        is_connected = False
    finally:
        # --- 정리 작업은 동일하게 유지 ---
        logger.info(f"[{client_info}] WebSocket 정리 시작...")
        is_connected = False # 플래그가 false인지 확인

        # 1. STT 태스크 취소
        if stt_task and not stt_task.done():
            logger.info(f"[{client_info}] STT 서비스 태스크 취소 중...")
            stt_task.cancel()
            try: await stt_task
            except asyncio.CancelledError: logger.info(f"[{client_info}] STT 서비스 태스크 성공적으로 취소됨.")
            except Exception as e_stt_final: logger.error(f"[{client_info}] STT 태스크 취소 대기 중 오류 발생: {e_stt_final}", exc_info=True)

        # 2. LLM/TTS 태스크 취소
        if llm_tts_tasks:
            logger.info(f"[{client_info}] {len(llm_tts_tasks)}개의 LLM->청커->TTS 태스크 취소 중...")
            tasks_to_await = list(llm_tts_tasks)
            for task in tasks_to_await:
                if not task.done(): task.cancel()
            results = await asyncio.gather(*tasks_to_await, return_exceptions=True)
            for i, result in enumerate(results):
                 task_name = tasks_to_await[i].get_name() if hasattr(tasks_to_await[i], 'get_name') else f"LLM-TTS-Task-{i}"
                 if isinstance(result, asyncio.CancelledError): logger.info(f"[{client_info}] {task_name} 성공적으로 취소됨.")
                 elif isinstance(result, Exception): logger.error(f"[{client_info}] {task_name} 정리 중 오류 발생: {result}", exc_info=result)

        # 3. 오디오 큐가 비어있는지 확인
        if audio_queue:
             try: await asyncio.wait_for(audio_queue.put(None), timeout=0.1)
             except Exception: pass
             while not audio_queue.empty():
                  try:
                       audio_queue.get_nowait()
                       audio_queue.task_done()
                  except (asyncio.QueueEmpty, ValueError): break

        # 4. WebSocket 닫기
        try:
            if websocket.client_state == WebSocketState.CONNECTED:
                logger.info(f"[{client_info}] WebSocket 연결 명시적으로 닫기 (코드 1000)...")
                await websocket.close(code=1000)
            elif websocket.client_state == WebSocketState.DISCONNECTED:
                 logger.info(f"[{client_info}] WebSocket이 이미 연결이 끊어졌습니다.")
            else:
                 logger.warning(f"[{client_info}] 정리 중 WebSocket이 예상치 못한 상태: {websocket.client_state}")
        except Exception as e_close_final:
            logger.warning(f"[{client_info}] 최종 정리 중 WebSocket 닫기 오류: {e_close_final}", exc_info=True)

        logger.info(f"WebSocket 연결 정리 완료: {client_info}")
