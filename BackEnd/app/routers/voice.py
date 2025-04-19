# backend/app/routers/voice.py
import logging
import asyncio
from fastapi import APIRouter, WebSocket, WebSocketDisconnect
from starlette.websockets import WebSocketState
from app.services.stt_service import handle_stt_stream, STTTimeoutError
from app.services.llm_service import stream_llm_response
from app.services.tts_service import synthesize_speech_stream # 업데이트된 TTS 서비스 임포트
from google.api_core import exceptions as google_exceptions
from typing import Set
import os # 오류 확인을 위한 임포트

# 로거 설정
logger = logging.getLogger(__name__)

# APIRouter 인스턴스
router = APIRouter(
    prefix="/ws",
    tags=["voice"],
)

@router.websocket("/audio")
async def websocket_endpoint(websocket: WebSocket):
    """
    WebSocket 연결을 처리하고, 오디오 수신 -> STT -> LLM -> TTS -> 오디오 전송 파이프라인을 관리합니다.
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

    # --- LLM 및 TTS 처리 함수 ---
    async def handle_llm_and_tts(transcript: str, ws: WebSocket, client_id: str):
        """LLM 응답을 받아 TTS로 변환하고 WebSocket으로 오디오 청크를 전송합니다."""
        # *** 수정: 외부 스코프 변수를 수정하기 위해 is_connected를 nonlocal로 선언 ***
        nonlocal is_connected
        logger.info(f"[{client_id}] Starting LLM->TTS pipeline for final STT result: '{transcript[:50]}...'")
        llm_stream = None
        tts_stream = None
        try:
            # 1. LLM 서비스 호출하여 텍스트 스트림 받기
            llm_stream = stream_llm_response(transcript, client_id)

            # 2. TTS 서비스 호출하여 오디오 스트림 받기 (LLM 스트림을 직접 전달)
            tts_stream = synthesize_speech_stream(llm_stream) # 비동기 이터레이터 전달

            # 3. 오디오 청크를 WebSocket으로 스트리밍
            async for audio_chunk in tts_stream:
                # 전송 시도 전 연결 상태 확인
                if not is_connected:
                    logger.warning(f"[{client_id}] WebSocket disconnected (checked before send), stopping TTS audio transmission.")
                    break # 연결이 끊어졌으면 루프 종료

                try:
                    # 전송 직전 상태 재확인 (이중 확인)
                    if ws.client_state == WebSocketState.CONNECTED:
                        await ws.send_bytes(audio_chunk)
                        logger.debug(f"[{client_id}] TTS 오디오 청크 전송됨 ({len(audio_chunk)} bytes)")
                    else:
                        logger.warning(f"[{client_id}] WebSocket이 더 이상 연결되지 않았습니다. TTS 오디오 청크를 전송할 수 없습니다.")
                        is_connected = False # 플래그 업데이트
                        break
                except WebSocketDisconnect:
                    logger.warning(f"[{client_id}] TTS 오디오 청크 전송 중 WebSocket 연결이 끊어졌습니다.")
                    is_connected = False
                    break
                except Exception as e:
                    # 다른 잠재적 전송 오류 로깅 (예: 연결 재설정)
                    logger.warning(f"[{client_id}] TTS 오디오 청크 전송 중 오류: {e}")
                    # 이 오류가 연결 손실을 의미하는지 고려
                    if isinstance(e, (ConnectionResetError, BrokenPipeError)):
                         is_connected = False
                    # 오류 유형에 따라 중단 여부 결정
                    break # 대부분의 오류에서 전송 중단

            # 루프 종료 후 연결 상태에 따른 로깅
            if is_connected:
                logger.info(f"[{client_id}] LLM->TTS 오디오 스트리밍 완료.")
            else:
                logger.warning(f"[{client_id}] 연결 끊김으로 인해 LLM->TTS 오디오 스트리밍이 중단되었습니다.")


        except asyncio.CancelledError:
            logger.info(f"[{client_id}] LLM->TTS 파이프라인 태스크 취소됨.")
            # 필요한 경우 관련 스트림(수동 관리되는 경우) 정리
        except Exception as e:
            logger.error(f"[{client_id}] LLM->TTS 파이프라인 처리 중 오류 발생: {e}", exc_info=True)
            # 선택적으로 클라이언트에게 알림
            if is_connected and ws.client_state == WebSocketState.CONNECTED:
                try:
                    error_message = f"응답 처리 중 서버 오류: {type(e).__name__}"
                    await ws.send_text(f'{{"error": "{error_message}"}}') # JSON 오류 전송
                except Exception as send_err:
                     logger.warning(f"[{client_id}] Failed to send error message to client: {send_err}")
        finally:
             # 태스크 제거는 add_done_callback에서 처리됨
             logger.debug(f"[{client_id}] LLM->TTS pipeline task finished execution.")


    # --- STT 결과 처리 콜백 ---
    async def process_stt_result(transcript: str, is_final: bool):
        """STT 결과를 처리하는 콜백 함수. 최종 결과에서 LLM->TTS 파이프라인을 시작합니다."""
        nonlocal llm_tts_tasks # 외부 스코프의 태스크 집합 사용
        # 외부 스코프의 is_connected 플래그 사용
        if not is_connected:
            logger.warning(f"[{client_info}] STT result received but WebSocket is disconnected. Ignoring.")
            return

        if not is_final:
            logger.debug(f"[{client_info}] Interim STT result: {transcript}")
            # 선택적으로 중간 결과 전송 (JSON 텍스트)
            # try:
            #     if websocket.client_state == WebSocketState.CONNECTED:
            #         await websocket.send_text(f'{{"transcript": "{transcript}", "is_final": false}}')
            # except Exception: pass
        else:
            logger.info(f"[{client_info}] Final STT result: {transcript}")
            # 선택적으로 최종 텍스트 결과 전송
            # try:
            #     if websocket.client_state == WebSocketState.CONNECTED:
            #          await websocket.send_text(f'{{"transcript": "{transcript}", "is_final": true}}')
            # except Exception: pass

            # 비어있지 않은 최종 결과만 처리
            if transcript and transcript.strip():
                # LLM->TTS 파이프라인을 별도 태스크로 시작
                llm_tts_task = asyncio.create_task(
                    handle_llm_and_tts(transcript, websocket, client_info)
                )
                llm_tts_tasks.add(llm_tts_task)
                # 완료/취소 시 태스크를 집합에서 제거하는 콜백 추가
                llm_tts_task.add_done_callback(llm_tts_tasks.discard)
                logger.debug(f"[{client_info}] LLM->TTS pipeline task created: {llm_tts_task.get_name()}")
            else:
                logger.info(f"[{client_info}] Empty final STT result. Skipping LLM->TTS pipeline.")


    # --- 메인 루프: STT 관리 및 메시지 수신 ---
    try:
        while is_connected:
            # 1. STT 태스크 관리 (시작 또는 재시작)
            if stt_task is None or stt_task.done():
                should_restart_stt = False
                if stt_task and stt_task.done():
                    try:
                        stt_task.result() # 완료된 태스크의 예외 확인
                        # STT 태스크가 오류 없이 종료된 경우 (예: None 신호),
                        # 여전히 '연결된' 상태라면 재시작할지 또는 루프를 종료할지 결정
                        # 현재 로직은 should_restart_stt가 True일 때 재시작
                    except STTTimeoutError:
                        logger.info(f"[{client_info}] STT timeout detected. Will restart STT service.")
                        should_restart_stt = True
                    except google_exceptions.InternalServerError as e_internal:
                         logger.warning(f"[{client_info}] STT service internal server error (500): {e_internal}. Will attempt restart.")
                         should_restart_stt = True
                    except asyncio.CancelledError:
                        logger.info(f"[{client_info}] Previous STT task was cancelled.")
                        if is_connected: should_restart_stt = True # 취소되었지만 여전히 연결된 경우 재시작
                    except Exception as e:
                        logger.error(f"[{client_info}] Unhandled exception in previous STT task: {e}. Closing connection.", exc_info=True)
                        is_connected = False # 처리되지 않은 STT 오류 시 연결 종료

                # 필요하고 여전히 연결된 경우 STT 시작/재시작
                if is_connected and (stt_task is None or should_restart_stt):
                    logger.info(f"[{client_info}] (Re)starting STT service task...")
                    # STT 재시작 전에 큐를 비움
                    while not audio_queue.empty():
                        try:
                            audio_queue.get_nowait()
                            audio_queue.task_done()
                        except (asyncio.QueueEmpty, ValueError): break
                    logger.debug(f"[{client_info}] Cleared audio queue before restarting STT.")

                    stt_task = asyncio.create_task(
                        handle_stt_stream(audio_queue, process_stt_result)
                    )
                    await asyncio.sleep(0.1) # 짧은 일시 중지

            # 2. WebSocket 메시지 수신 또는 STT 태스크 완료 대기
            if not is_connected: break # 연결이 끊어졌으면 루프 종료

            # 메시지 또는 STT 태스크 완료 대기
            tasks_to_wait = [asyncio.create_task(websocket.receive())]
            if stt_task and not stt_task.done():
                tasks_to_wait.append(stt_task)

            done, pending = await asyncio.wait(
                tasks_to_wait,
                return_when=asyncio.FIRST_COMPLETED
                # 여기서 타임아웃 제거, STT 타임아웃과 WebSocket keepalive에 의존
            )

            # 완료된 태스크 처리
            for task in done:
                if task == stt_task:
                     # STT 태스크 완료, 다음 반복에서 stt_task.done() 확인
                     logger.debug(f"[{client_info}] STT task completed its run (detected in wait).")
                     # 여기서도 오류 확인 필요
                     try:
                          task.result()
                     except STTTimeoutError:
                          logger.info(f"[{client_info}] STT timeout detected (from wait).")
                          # 루프가 재시작 처리
                     except google_exceptions.InternalServerError as e_internal:
                          logger.warning(f"[{client_info}] STT internal server error (500) detected (from wait): {e_internal}.")
                     except asyncio.CancelledError:
                          logger.info(f"[{client_info}] STT task cancelled (detected in wait).")
                     except Exception as e:
                          logger.error(f"[{client_info}] Unhandled STT exception (from wait): {e}. Closing.", exc_info=True)
                          is_connected = False
                     # 잠재적 재시작을 위해 다음 루프 반복으로 계속
                     continue

                # STT 태스크가 아니면 수신 태스크
                receive_task = task
                try:
                    data = receive_task.result() # 수신 태스크에서 데이터 가져오기
                    if isinstance(data, dict):
                        if data.get("type") == "websocket.disconnect":
                            logger.warning(f"[{client_info}] WebSocket disconnect message received: {data}. Closing.")
                            is_connected = False
                        elif "text" in data:
                            text_data = data["text"]
                            logger.info(f"[{client_info}] Text message received: {text_data}")
                            if text_data.lower() in ["client stopped recording", "disconnect", "stop"]:
                                logger.info(f"[{client_info}] Client stop signal received. Sending None to audio queue.")
                                if audio_queue:
                                    # None을 비차단적으로 또는 타임아웃과 함께 전송
                                    try:
                                        await asyncio.wait_for(audio_queue.put(None), timeout=1.0)
                                    except asyncio.TimeoutError:
                                         logger.warning(f"[{client_info}] Timeout putting None into audio queue.")
                                # STT가 None 신호를 처리하도록 하고 즉시 연결을 끊지 않음
                        elif "bytes" in data:
                            audio_chunk = data["bytes"]
                            if audio_chunk and audio_queue:
                                await audio_queue.put(audio_chunk)
                            else:
                                logger.debug(f"[{client_info}] Empty audio chunk received, ignored.")
                    else:
                        logger.warning(f"[{client_info}] Unexpected data type received: {type(data)}")

                except WebSocketDisconnect as e:
                    logger.warning(f"[{client_info}] WebSocket disconnected during receive: Code {e.code}, Reason: {e.reason}.")
                    is_connected = False
                except asyncio.CancelledError:
                     logger.info(f"[{client_info}] Receive task cancelled.")
                     is_connected = False # 연결이 닫히는 중으로 가정
                except Exception as e_recv:
                    logger.error(f"[{client_info}] Error during WebSocket receive: {e_recv}", exc_info=True)
                    is_connected = False

            # 대기 중인 태스크가 있으면 취소 (STT 태스크가 완료된 경우 수신 태스크만)
            for task in pending:
                 if task != stt_task: # STT 태스크가 대기 중이면 취소하지 않음
                      task.cancel()


    except WebSocketDisconnect as e:
        logger.warning(f"WebSocket connection closed externally: {client_info} - Code: {e.code}, Reason: {e.reason}")
        is_connected = False
    except asyncio.CancelledError:
        logger.info(f"[{client_info}] Main WebSocket handler task cancelled.")
        is_connected = False
    except Exception as e:
        logger.error(f"Unhandled exception in WebSocket handler ({client_info}): {e}", exc_info=True)
        is_connected = False
    finally:
        logger.info(f"[{client_info}] Starting WebSocket cleanup...")
        is_connected = False # 플래그가 false인지 확인

        # 1. STT 태스크 취소
        if stt_task and not stt_task.done():
            logger.info(f"[{client_info}] Cancelling STT service task...")
            stt_task.cancel()
            try:
                await stt_task
            except asyncio.CancelledError:
                logger.info(f"[{client_info}] STT service task successfully cancelled.")
            except Exception as e_stt_final:
                logger.error(f"[{client_info}] Error waiting for STT task cancellation: {e_stt_final}", exc_info=True)

        # 2. LLM/TTS 태스크 취소
        if llm_tts_tasks:
            logger.info(f"[{client_info}] Cancelling {len(llm_tts_tasks)} LLM->TTS tasks...")
            tasks_to_await = list(llm_tts_tasks)
            for task in tasks_to_await:
                if not task.done():
                    task.cancel()
            results = await asyncio.gather(*tasks_to_await, return_exceptions=True)
            # 취소/완료 결과 로깅
            for i, result in enumerate(results):
                 task_name = tasks_to_await[i].get_name() if hasattr(tasks_to_await[i], 'get_name') else f"LLM-TTS-Task-{i}"
                 if isinstance(result, asyncio.CancelledError):
                      logger.info(f"[{client_info}] {task_name} successfully cancelled.")
                 elif isinstance(result, Exception):
                      logger.error(f"[{client_info}] Error during {task_name} cleanup: {result}", exc_info=result)


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
                logger.info(f"[{client_info}] Closing WebSocket connection explicitly (code 1000)...")
                await websocket.close(code=1000)
            elif websocket.client_state == WebSocketState.DISCONNECTED:
                 logger.info(f"[{client_info}] WebSocket already disconnected.")
            else:
                 logger.warning(f"[{client_info}] WebSocket in unexpected state during cleanup: {websocket.client_state}")

        except Exception as e_close_final:
            logger.warning(f"[{client_info}] Error closing WebSocket during final cleanup: {e_close_final}", exc_info=True)

        logger.info(f"WebSocket connection cleanup finished for: {client_info}")
