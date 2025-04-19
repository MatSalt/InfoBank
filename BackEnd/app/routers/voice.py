# backend/app/routers/voice.py
import logging
import asyncio
from fastapi import APIRouter, WebSocket, WebSocketDisconnect # WebSocketState 임포트 제거
from app.services.stt_service import handle_stt_stream # STT 서비스 함수 임포트
from app.services.llm_service import stream_llm_response # LLM 서비스 함수 임포트
from app.services.tts_service import synthesize_speech_stream # TTS 서비스 임포트
from typing import Set # Set 타입 임포트

# 로거 설정 (main.py에서 설정된 로거 사용 또는 여기서 별도 설정 가능)
logger = logging.getLogger(__name__)

# APIRouter 인스턴스 생성
router = APIRouter(
    prefix="/ws", # 이 라우터의 모든 경로 앞에 /ws 접두사 추가
    tags=["voice"], # API 문서에서 태그별로 그룹화
)

@router.websocket("/audio")
async def websocket_endpoint(websocket: WebSocket):
    """
    WebSocket 연결을 처리하고, 오디오 수신 -> STT -> LLM -> TTS -> 오디오 전송 파이프라인을 관리합니다.
    """
    await websocket.accept() # 클라이언트의 웹소켓 연결 요청 수락
    client_host = websocket.client.host
    client_port = websocket.client.port
    client_info = f"{client_host}:{client_port}"
    logger.info(f"WebSocket 연결 수락됨: {client_info}")

    audio_queue = asyncio.Queue() # STT 입력 오디오 큐
    stt_task: asyncio.Task | None = None # STT 처리 태스크
    # LLM 및 TTS 처리를 위한 태스크 집합 (여러 요청 동시 처리 가능성 고려)
    llm_tts_tasks: Set[asyncio.Task] = set()

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
                if ws.client_state == "connected": # 연결 상태 확인 (WebSocketState 대신 문자열 사용)
                    await ws.send_bytes(audio_chunk)
                    logger.debug(f"[{client_id}] TTS 오디오 청크 전송됨 ({len(audio_chunk)} bytes)")
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
            #     if ws.client_state == "connected":
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
            #     if websocket.client_state == "connected":
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
            #     if websocket.client_state == "connected":
            #         await websocket.send_text(f"최종 인식: {transcript}")
            # except Exception: pass

    try:
        # --- STT 서비스 시작 ---
        stt_task = asyncio.create_task(
            handle_stt_stream(audio_queue, process_stt_result)
        )
        logger.info(f"[{client_info}] STT 서비스 태스크 시작됨.")

        # --- 클라이언트로부터 오디오 수신 ---
        while True:
            # 연결 상태 확인 후 수신 시도
            if websocket.client_state != "connected": # WebSocketState 대신 문자열 사용
                 logger.warning(f"[{client_info}] WebSocket 연결이 끊어진 상태에서 수신 시도 방지.")
                 break

            data = await websocket.receive() # 클라이언트로부터 메시지 수신 대기

            if "bytes" in data: # 오디오 청크 수신
                audio_chunk = data["bytes"]
                if audio_chunk:
                    logger.debug(f"[{client_info}] 오디오 청크 수신: {len(audio_chunk)} bytes")
                    await audio_queue.put(audio_chunk)
                    logger.debug(f"[{client_info}] 오디오 청크를 큐에 추가 완료.")
                else:
                     logger.debug(f"[{client_info}] 빈 오디오 청크 수신, 무시함.")

            elif "text" in data: # 텍스트 메시지 수신
                text_data = data["text"]
                logger.info(f"[{client_info}] 텍스트 메시지 수신: {text_data}")
                if text_data.lower() in ["client stopped recording", "disconnect", "stop"]:
                    logger.info(f"[{client_info}] 클라이언트가 중지 신호 보냄. 스트림 종료 중.")
                    break # 오디오 수신 루프 종료

    except WebSocketDisconnect as e:
        logger.warning(f"WebSocket 연결 끊김: {client_info} - 코드: {e.code}, 이유: {e.reason}")
    except asyncio.CancelledError:
         logger.info(f"[{client_info}] WebSocket 핸들러 태스크 취소됨.")
         # 명시적으로 닫기 시도
         try:
             if websocket.client_state == "connected": # WebSocketState 대신 문자열 사용
                 await websocket.close(code=1001, reason="Server shutting down")
         except Exception: pass
    except Exception as e:
        logger.error(f"WebSocket 연결 중 오류 발생 ({client_info}): {e}", exc_info=True)
        try:
            if websocket.client_state == "connected": # WebSocketState 대신 문자열 사용
                await websocket.close(code=1011, reason=f"Server error: {e}")
        except Exception: pass
    finally:
        logger.info(f"[{client_info}] WebSocket 연결 정리 시작...")

        # 1. STT 서비스에게 오디오 전송 중단 신호 보내기
        if audio_queue:
             logger.debug(f"[{client_info}] 오디오 큐에 종료 신호(None) 전송 시도...")
             try:
                 # 큐가 가득 찼을 경우를 대비해 타임아웃 설정 고려 가능
                 await asyncio.wait_for(audio_queue.put(None), timeout=5.0)
                 logger.debug(f"[{client_info}] 오디오 큐에 종료 신호 전송 완료.")
             except asyncio.TimeoutError:
                 logger.warning(f"[{client_info}] 오디오 큐에 종료 신호 전송 시간 초과.")
             except Exception as e:
                 logger.error(f"[{client_info}] 오디오 큐에 종료 신호 전송 중 오류: {e}", exc_info=True)

        # 2. STT 처리 태스크 취소 및 대기
        if stt_task and not stt_task.done():
            logger.info(f"[{client_info}] STT 서비스 태스크 취소 시도...")
            stt_task.cancel()
            try:
                await stt_task
            except asyncio.CancelledError:
                logger.info(f"[{client_info}] STT 서비스 태스크 성공적으로 취소됨.")
            except Exception as e:
                 logger.error(f"[{client_info}] STT 태스크 종료 대기 중 오류 발생: {e}", exc_info=True)
        else:
             logger.info(f"[{client_info}] STT 태스크가 이미 완료되었거나 존재하지 않음.")

        # 3. 실행 중인 모든 LLM->TTS 태스크 취소 및 대기
        if llm_tts_tasks:
            logger.info(f"[{client_info}] 실행 중인 LLM->TTS 태스크 {len(llm_tts_tasks)}개 취소 시도...")
            tasks_to_await = list(llm_tts_tasks) # 반복 중 수정을 피하기 위해 리스트 복사
            for task in tasks_to_await:
                if not task.done():
                    task.cancel()
            # 모든 태스크가 완료될 때까지 기다림 (취소 포함)
            results = await asyncio.gather(*tasks_to_await, return_exceptions=True)
            for i, result in enumerate(results):
                task_name = tasks_to_await[i].get_name() if hasattr(tasks_to_await[i], 'get_name') else f"LLM-TTS-Task-{i}"
                if isinstance(result, asyncio.CancelledError):
                    logger.info(f"[{client_info}] {task_name} 성공적으로 취소됨.")
                elif isinstance(result, Exception):
                    logger.error(f"[{client_info}] {task_name} 종료 중 오류 발생: {result}", exc_info=result)
                # else: # 정상 종료 로그는 handle_llm_and_tts 내부에서 처리
                #     logger.info(f"[{client_info}] {task_name} 정상 종료됨.")
        else:
            logger.info(f"[{client_info}] 실행 중인 LLM->TTS 태스크 없음.")

        # 4. 웹소켓 연결 닫기 (이미 닫히지 않았다면)
        try:
            if websocket.client_state == "connected": # WebSocketState 대신 문자열 사용
                 logger.info(f"[{client_info}] WebSocket 연결 명시적으로 닫기 시도...")
                 await websocket.close()
                 logger.info(f"[{client_info}] WebSocket 연결 명시적으로 닫힘.")
            else:
                 logger.info(f"[{client_info}] WebSocket 연결이 이미 닫힌 상태({websocket.client_state}).")
        except Exception as e:
            logger.warning(f"[{client_info}] WebSocket 닫기 중 오류 발생 (이미 닫혔을 수 있음): {e}")

        logger.info(f"WebSocket 연결 종료됨: {client_info}")
