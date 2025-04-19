# backend/app/routers/voice.py
import logging
import asyncio
from fastapi import APIRouter, WebSocket, WebSocketDisconnect
from starlette.websockets import WebSocketState
from app.services.stt_service import handle_stt_stream, STTTimeoutError
from app.services.llm_service import stream_llm_response
from app.services.tts_service import synthesize_speech_stream # TTS 서비스 임포트
from google.api_core import exceptions as google_exceptions
from typing import Set # Set 타입 임포트

# 로거 설정
logger = logging.getLogger(__name__)

# APIRouter 인스턴스 생성
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
    # LLM 및 TTS 처리를 위한 태스크 집합 (여러 요청 동시 처리 가능성 고려)
    llm_tts_tasks: Set[asyncio.Task] = set()
    
    # 연결 상태 플래그
    is_connected = True

    # --- LLM 및 TTS 처리 함수 ---
    async def handle_llm_and_tts(transcript: str, ws: WebSocket, client_id: str):
        """LLM 응답을 받아 TTS로 변환하고 WebSocket으로 오디오 청크를 전송합니다."""
        logger.info(f"[{client_id}] 최종 STT 결과로 LLM->TTS 파이프라인 시작: '{transcript[:50]}...'")
        try:
            # 1. LLM 서비스 호출하여 텍스트 스트림 받기
            text_chunk_stream = stream_llm_response(transcript, client_id)

            # 2. TTS 서비스 호출하여 오디오 스트림 받기
            audio_chunk_stream = synthesize_speech_stream(text_chunk_stream)

            # 3. 오디오 스트림을 WebSocket으로 전송
            async for audio_chunk in audio_chunk_stream:
                if is_connected: # 연결 상태 플래그 사용
                    try:
                        await ws.send_bytes(audio_chunk)
                        logger.debug(f"[{client_id}] TTS 오디오 청크 전송됨 ({len(audio_chunk)} bytes)")
                    except Exception as e:
                        logger.warning(f"[{client_id}] TTS 오디오 청크 전송 중 오류 발생: {e}")
                        break
                else:
                    logger.warning(f"[{client_id}] WebSocket 연결이 끊어져 TTS 오디오 전송 중단.")
                    break # 연결 끊겼으면 루프 종료
            logger.info(f"[{client_id}] LLM->TTS 오디오 스트림 전송 완료.")

        except asyncio.CancelledError:
            logger.info(f"[{client_id}] LLM->TTS 파이프라인 태스크 취소됨.")
        except Exception as e:
            logger.error(f"[{client_id}] LLM->TTS 파이프라인 처리 중 오류 발생: {e}", exc_info=True)
            # 클라이언트에게 오류 알림 (선택 사항)
            # try:
            #     if is_connected:
            #         await ws.send_text(f"Error processing response: {e}")
            # except Exception: pass # 오류 전송 실패는 무시

    # --- STT 결과 처리 콜백 함수 ---
    async def process_stt_result(transcript: str, is_final: bool):
        """STT 결과를 처리하고, 최종 결과는 LLM->TTS 파이프라인을 시작하는 콜백 함수"""
        nonlocal llm_tts_tasks # 외부 함수의 llm_tts_tasks 변수 사용 명시

        if not is_final:
            logger.debug(f"[{client_info}] 중간 결과: {transcript}")
            # 필요시 중간 결과를 클라이언트에게 전송 (텍스트)
            # try:
            #     if is_connected:
            #         await websocket.send_text(f"중간 인식: {transcript}")
            # except Exception: pass
        else:
            logger.info(f"[{client_info}] 최종 결과: {transcript}")
            if transcript.strip(): # 빈 문자열이 아닌 경우에만 처리
                # LLM->TTS 파이프라인을 별도 태스크로 실행
                llm_tts_task = asyncio.create_task(
                    handle_llm_and_tts(transcript, websocket, client_info)
                )
                llm_tts_tasks.add(llm_tts_task) # 태스크 집합에 추가
                # 태스크 완료 시 집합에서 제거하는 콜백 추가
                llm_tts_task.add_done_callback(llm_tts_tasks.discard)
                logger.debug(f"[{client_info}] LLM->TTS 파이프라인 태스크 생성됨: {llm_tts_task.get_name()}")
            else:
                logger.info(f"[{client_info}] 최종 결과가 비어있어 LLM->TTS 파이프라인을 시작하지 않음.")
            # 최종 텍스트 결과를 클라이언트에게 전송할 수도 있음 (디버깅 등 목적)
            # try:
            #     if is_connected:
            #         await websocket.send_text(f"최종 인식: {transcript}")
            # except Exception: pass

    try:
        # --- 메인 루프: STT 관리 및 메시지 수신 ---
        while is_connected:
            # 1. STT 태스크 관리 (시작 또는 재시작)
            if stt_task is None or stt_task.done():
                should_restart_stt = False  # STT 재시작 여부 플래그
                if stt_task and stt_task.done():
                    try:
                        stt_task.result()  # 예외 발생 여부 확인
                        # 오류 없이 정상 종료된 경우 (예: 클라이언트 중지 신호)
                        # is_connected 플래그가 False가 아니면 재시작할 수도 있음
                    except STTTimeoutError:
                        logger.info(f"[{client_info}] STT 타임아웃 감지. STT 서비스를 재시작합니다.")
                        should_restart_stt = True
                    except google_exceptions.InternalServerError as e_internal:
                        logger.warning(f"[{client_info}] STT 서비스 내부 서버 오류(500) 발생: {e_internal}. 재연결 시도.")
                        should_restart_stt = True  # 500 오류도 재시작 시도
                    except asyncio.CancelledError:
                        logger.info(f"[{client_info}] 이전 STT 태스크가 취소되었습니다.")
                        # 취소된 경우, 연결이 끊기지 않았다면 재시작할 수 있음
                        if is_connected:
                            should_restart_stt = True
                    except Exception as e:
                        logger.error(f"[{client_info}] 이전 STT 태스크에서 예상치 못한 오류 발생: {e}. 연결 종료 시도.", exc_info=True)
                        is_connected = False  # 처리할 수 없는 오류 시 연결 종료

                # STT 태스크 (재)시작 조건: (처음 시작) 또는 (재시작 플래그 True 이고 연결 유지 상태)
                if is_connected and (stt_task is None or should_restart_stt):
                    logger.info(f"[{client_info}] STT 서비스 태스크 (재)시작...")
                    stt_task = asyncio.create_task(
                        handle_stt_stream(audio_queue, process_stt_result)
                    )
                    await asyncio.sleep(0.1)  # 재시작 전 짧은 대기

            # 2. 웹소켓 메시지 수신 및 처리
            try:
                try:
                    data = await asyncio.wait_for(websocket.receive(), timeout=1.0)
                except asyncio.TimeoutError:
                    continue

                if isinstance(data, dict):
                    if data.get("type") == "websocket.disconnect":
                        logger.warning(f"[{client_info}] WebSocket disconnect 메시지 수신: {data}. 루프 종료.")
                        is_connected = False
                        break
                    elif "text" in data:
                        text_data = data["text"]
                        logger.info(f"[{client_info}] 텍스트 메시지 수신: {text_data}")
                        if text_data.lower() in ["client stopped recording", "disconnect", "stop"]:
                            logger.info(f"[{client_info}] 클라이언트 중지 신호 수신. STT 종료 신호 전송 및 루프 종료.")
                            if audio_queue:
                                await asyncio.wait_for(audio_queue.put(None), timeout=1.0)
                            is_connected = False
                            break
                    elif "bytes" in data:
                        audio_chunk = data["bytes"]
                        if audio_chunk:
                            await audio_queue.put(audio_chunk)
                        else:
                            logger.debug(f"[{client_info}] 빈 오디오 청크 수신, 무시함.")
                else:
                    logger.warning(f"[{client_info}] 예상치 못한 데이터 형식 수신: {type(data)}")

            except WebSocketDisconnect as e:
                logger.warning(f"[{client_info}] WebSocketDisconnect 예외 발생: 코드 {e.code}, 이유: {e.reason}. 루프 종료.")
                is_connected = False
            except RuntimeError as e:
                if "Cannot call \"receive\"" in str(e):
                    logger.warning(f"[{client_info}] 이미 연결이 끊긴 후 receive() 호출 시도: {e}. 루프 종료.")
                else:
                    logger.error(f"[{client_info}] 데이터 수신/처리 중 예상치 못한 RuntimeError: {e}", exc_info=True)
                is_connected = False
                break
            except Exception as e_inner:
                logger.error(f"[{client_info}] 데이터 수신/처리 중 예외 발생: {e_inner}", exc_info=True)
                is_connected = False

    except WebSocketDisconnect as e:
        logger.warning(f"WebSocket 연결 외부 루프에서 끊김 감지: {client_info} - 코드: {e.code}, 이유: {e.reason}")
        is_connected = False
    except asyncio.CancelledError:
        logger.info(f"[{client_info}] WebSocket 핸들러 태스크 취소됨.")
        is_connected = False
        try:
            await websocket.close(code=1001, reason="Server shutting down")
        except Exception: pass
    except Exception as e:
        logger.error(f"WebSocket 연결 중 오류 발생 ({client_info}): {e}", exc_info=True)
        is_connected = False
        try:
            await websocket.close(code=1011, reason=f"Server error: {e}")
        except Exception: pass
    finally:
        logger.info(f"[{client_info}] WebSocket 연결 정리 시작...")
        is_connected = False

        # 1. STT 태스크 취소 시도
        if stt_task and not stt_task.done():
            logger.info(f"[{client_info}] STT 서비스 태스크 취소 시도...")
            stt_task.cancel()
            try:
                await stt_task
            except asyncio.CancelledError:
                logger.info(f"[{client_info}] STT 서비스 태스크 성공적으로 취소됨.")
            except STTTimeoutError:
                logger.info(f"[{client_info}] 종료 시 STT 태스크에서 타임아웃 오류 확인됨 (무시).")
            except google_exceptions.InternalServerError:
                logger.info(f"[{client_info}] 종료 시 STT 태스크에서 내부 서버 오류 확인됨 (무시).")
            except Exception as e_stt_final:
                logger.error(f"[{client_info}] STT 태스크 종료 대기 중 오류 발생: {e_stt_final}", exc_info=True)

        # 2. LLM/TTS 태스크 정리
        if llm_tts_tasks:
            logger.info(f"[{client_info}] 실행 중인 LLM->TTS 태스크 {len(llm_tts_tasks)}개 취소 시도...")
            tasks_to_await = list(llm_tts_tasks)
            for task in tasks_to_await:
                if not task.done():
                    task.cancel()
            results = await asyncio.gather(*tasks_to_await, return_exceptions=True)
            for i, result in enumerate(results):
                task_name = tasks_to_await[i].get_name() if hasattr(tasks_to_await[i], 'get_name') else f"LLM-TTS-Task-{i}"
                if isinstance(result, asyncio.CancelledError):
                    logger.info(f"[{client_info}] {task_name} 성공적으로 취소됨.")
                elif isinstance(result, Exception):
                    logger.error(f"[{client_info}] {task_name} 종료 중 오류 발생: {result}", exc_info=result)

        # 3. 웹소켓 닫기
        try:
            current_state_final = websocket.application_state
            if current_state_final == WebSocketState.CONNECTED:
                logger.info(f"[{client_info}] finally 블록: WebSocket 연결 명시적으로 닫기 시도...")
                await websocket.close(code=1000)
                logger.info(f"[{client_info}] finally 블록: WebSocket 연결 명시적으로 닫힘.")
        except Exception as e_close_final:
            logger.warning(f"[{client_info}] WebSocket 닫기 중 예기치 않은 오류 발생: {e_close_final}", exc_info=True)

        logger.info(f"WebSocket 연결 종료됨: {client_info}")
