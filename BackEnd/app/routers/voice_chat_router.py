# backend/app/routers/voice.py
import logging
import asyncio
import re # 정규식 임포트 (현재 로직에서는 필수는 아니지만 향후 사용을 위해)
import uuid # 사용자 ID 생성을 위한 UUID 모듈 추가
from fastapi import APIRouter, WebSocket, WebSocketDisconnect
from starlette.websockets import WebSocketState
from app.services.stt_service import handle_stt_stream, start_stt_with_auto_reconnect, STTTimeoutError  # 자동 재연결 함수 추가
from app.services.llm_service import stream_llm_response, clear_user_session # clear_user_session 함수 추가
from app.services.tts_service import synthesize_speech_stream # 업데이트된 TTS 서비스 임포트
from app.services.llm_emotion_service import analyze_emotion  # 감정 분석 서비스 추가
from app.utils.text_processor import chunk_text_by_punctuation  # 텍스트 처리 함수 임포트
from app.utils.pipeline_manager import handle_llm_and_tts, handle_emotion_analysis  # 파이프라인 관리 함수 임포트
from app.utils.websocket_utils import handle_interruption, send_json_message  # WebSocket 유틸리티 함수 임포트
from google.api_core import exceptions as google_exceptions
# google.generativeai.errors 임포트 오류 수정
# 대신 google.api_core.exceptions를 사용하여 429 오류를 처리
from typing import Set, AsyncIterator # AsyncIterator 임포트
import os # 오류 확인을 위한 임포트
import time # 시간 관련 함수를 위한 임포트

# 로거 설정
logger = logging.getLogger(__name__)

# APIRouter 인스턴스
router = APIRouter(
    prefix="/ws",
    tags=["voice"],
)

# --- 텍스트 청킹 함수는 app.utils.text_processor 모듈로 이동되었음 ---

@router.websocket("/audio")
async def websocket_endpoint(websocket: WebSocket):
    """
    WebSocket 연결을 처리하고, 오디오 수신 -> STT -> LLM -> 텍스트 청킹 -> TTS -> 오디오 전송 파이프라인을 관리합니다.
    """
    await websocket.accept()
    client_host = websocket.client.host
    client_port = websocket.client.port
    client_info = f"{client_host}:{client_port}"
    
    # 사용자 ID 생성 (UUID 사용)
    user_id = str(uuid.uuid4())
    logger.info(f"WebSocket 연결 수락됨: {client_info} (사용자 ID: {user_id})")

    audio_queue = asyncio.Queue() # STT 입력 오디오 큐
    stt_task: asyncio.Task | None = None # STT 처리 태스크
    llm_tts_tasks: Set[asyncio.Task] = set() # LLM/TTS 처리 태스크 집합

    # 연결 상태 플래그 - 외부 스코프에서 정의
    is_connected = True

    # --- 파이프라인 처리 함수는 app.utils.pipeline_manager 모듈로 이동됨 ---
    # --- 인터럽션 처리 함수는 app.utils.websocket_utils 모듈로 이동됨 ---

    # --- STT 결과 처리 콜백 ---
    async def process_stt_result(transcript: str, is_final: bool, speech_event=None):
        """STT 결과 또는 음성 활동 이벤트를 처리합니다."""
        nonlocal is_connected, llm_tts_tasks
        
        if not is_connected:
            logger.warning(f"[{client_info}] 연결이 끊어진 상태에서 STT 결과 또는 이벤트 수신. 무시합니다.")
            return
        
        # 음성 활동 이벤트 처리
        if speech_event and isinstance(speech_event, dict):
            event_type = speech_event.get("type")
            
            logger.info(f"[{client_info}] 이벤트 처리: {event_type}")
            
            # 인터럽션 신호 처리 (response 객체 기반)
            if event_type == "INTERRUPTION_SIGNAL":
                logger.info(f"[{client_info}] 인터럽션 신호 감지: 인터럽션 처리")
                
                # 인터럽션 처리 전에 클라이언트에 알림
                if is_connected and websocket.client_state == WebSocketState.CONNECTED:
                    try:
                        await websocket.send_json({
                            "control": "interruption",
                            "status": "detected", 
                            "message": "새로운 질문을 말씀해주세요"
                        })
                        logger.info(f"[{client_info}] 인터럽션 감지 알림을 클라이언트에 전송함")
                    except Exception as e:
                        logger.error(f"[{client_info}] 인터럽션 알림 전송 중 오류: {e}")
                
                # 아바타가 말하는 중이라면 인터럽션 처리 함수 호출
                is_avatar_speaking = len(llm_tts_tasks) > 0
                if is_avatar_speaking:
                    # 인터럽션 처리 함수 호출
                    await handle_interruption(websocket, client_info, is_connected, llm_tts_tasks)
                return  # 인터럽션 처리 후 종료
            
            # STT 재연결 관련 이벤트 처리 (새로 추가)
            elif event_type == "STT_RECONNECTING":
                logger.info(f"[{client_info}] STT 재연결 중: 시도 #{speech_event.get('attempt')}/{speech_event.get('max_attempts')}")
                
                # 클라이언트에 STT 재연결 중임을 알림
                if is_connected and websocket.client_state == WebSocketState.CONNECTED:
                    try:
                        await websocket.send_json({
                            "control": "stt_status",
                            "status": "reconnecting",
                            "attempt": speech_event.get('attempt', 1),
                            "max_attempts": speech_event.get('max_attempts', 5)
                        })
                        logger.info(f"[{client_info}] STT 재연결 상태를 클라이언트에 전송함")
                    except Exception as e:
                        logger.error(f"[{client_info}] STT 재연결 알림 전송 중 오류: {e}")
                return  # 이벤트 처리 후 종료
            
            elif event_type == "STT_RECONNECTED":
                logger.info(f"[{client_info}] STT 재연결 성공: 시도 #{speech_event.get('attempt')}")
                
                # 클라이언트에 STT 재연결 성공을 알림
                if is_connected and websocket.client_state == WebSocketState.CONNECTED:
                    try:
                        await websocket.send_json({
                            "control": "stt_status",
                            "status": "reconnected",
                            "message": "음성 인식 서비스가 재연결되었습니다."
                        })
                    except Exception as e:
                        logger.error(f"[{client_info}] STT 재연결 성공 알림 전송 중 오류: {e}")
                return  # 이벤트 처리 후 종료
            
            elif event_type == "STT_RECONNECTION_FAILED":
                logger.error(f"[{client_info}] STT 재연결 실패: {speech_event.get('message')}")
                
                # 클라이언트에 STT 재연결 실패를 알림
                if is_connected and websocket.client_state == WebSocketState.CONNECTED:
                    try:
                        await websocket.send_json({
                            "control": "stt_status",
                            "status": "error",
                            "message": "음성 인식 서비스 연결 실패. 잠시 후 다시 시도해주세요.",
                            "error": speech_event.get('message', '최대 재시도 횟수 초과')
                        })
                    except Exception as e:
                        logger.error(f"[{client_info}] STT 재연결 실패 알림 전송 중 오류: {e}")
                return  # 이벤트 처리 후 종료
            
            elif event_type == "STT_ERROR":
                logger.error(f"[{client_info}] STT 서비스 오류: {speech_event.get('error')}")
                
                # 클라이언트에 STT 오류를 알림
                if is_connected and websocket.client_state == WebSocketState.CONNECTED:
                    try:
                        await websocket.send_json({
                            "control": "stt_status",
                            "status": "error",
                            "message": "음성 인식 서비스 오류. 잠시 후 다시 시도해주세요.",
                            "error": speech_event.get('error', '알 수 없는 오류')
                        })
                    except Exception as e:
                        logger.error(f"[{client_info}] STT 오류 알림 전송 중 오류: {e}")
                return  # 이벤트 처리 후 종료
            
            return  # 이벤트 처리 후 종료
        
        # 기존 텍스트 처리 코드
        if not transcript or not is_final:
            return  # 빈 텍스트나 중간 결과는 무시
        
        logger.info(f"[{client_info}] 최종 STT 결과 수신: '{transcript[:50]}...'")
        
        # 이전 LLM/TTS 태스크 취소 및 정리 (세트의 복사본을 사용하여 순회)
        tasks_to_cancel = list(llm_tts_tasks)  # 세트의 복사본 생성
        for task in tasks_to_cancel:
            if not task.done():
                task.cancel()
                try:
                    await task
                except asyncio.CancelledError:
                    pass
                except Exception as e:
                    logger.warning(f"[{client_info}] 이전 LLM/TTS 태스크 취소 중 오류: {e}")
        
        llm_tts_tasks.clear()  # 모든 태스크 제거
        
        # 새 LLM/TTS 태스크 시작
        dialog_task = asyncio.create_task(handle_llm_and_tts(transcript, websocket, client_info, user_id, is_connected))
        llm_tts_tasks.add(dialog_task)
        dialog_task.add_done_callback(lambda t: llm_tts_tasks.discard(t))
        
        # 감정 분석 태스크 시작 (추가)
        emotion_task = asyncio.create_task(handle_emotion_analysis(transcript, websocket, client_info))
        llm_tts_tasks.add(emotion_task)
        emotion_task.add_done_callback(lambda t: llm_tts_tasks.discard(t))

    # --- 메인 루프: STT 관리 및 메시지 수신 ---
    try:
        # STT 태스크 시작 (자동 재연결 기능 적용)
        stt_task = asyncio.create_task(start_stt_with_auto_reconnect(audio_queue, process_stt_result))
        
        # 메시지 수신 루프
        while is_connected:
            try:
                # 타임아웃 설정으로 무한 대기 방지
                message = await asyncio.wait_for(websocket.receive(), timeout=30.0)
                
                # 연결 상태 확인
                if not is_connected or websocket.client_state != WebSocketState.CONNECTED:
                    logger.warning(f"[{client_info}] 연결이 끊어진 상태에서 데이터 수신. 루프 종료.")
                    break
                
                # 메시지 타입에 따라 처리
                if "bytes" in message:
                    # 바이너리 데이터 처리 (오디오)
                    data = message["bytes"]
                    await audio_queue.put(data)
                    logger.debug(f"[{client_info}] 오디오 데이터 수신 및 큐에 추가됨 ({len(data)} bytes)")
                elif "text" in message:
                    # 텍스트 메시지 처리
                    text_data = message["text"]
                    logger.debug(f"[{client_info}] 텍스트 메시지 수신: {text_data}")
                    # 필요시 텍스트 메시지 처리 코드 추가
                    # 예: JSON 명령어 처리 등
                else:
                    # 알 수 없는 메시지 형식
                    logger.warning(f"[{client_info}] 알 수 없는 메시지 형식: {message}")
                
            except asyncio.TimeoutError:
                # 타임아웃은 정상적인 상황, 연결 상태 확인만
                if not is_connected or websocket.client_state != WebSocketState.CONNECTED:
                    logger.warning(f"[{client_info}] 연결이 끊어진 상태에서 타임아웃 발생. 루프 종료.")
                    break
                logger.debug(f"[{client_info}] 메시지 수신 타임아웃 (정상)")
                
            except WebSocketDisconnect:
                logger.info(f"[{client_info}] WebSocket 연결이 끊어짐")
                is_connected = False
                break
                
            except Exception as e:
                logger.error(f"[{client_info}] 메시지 수신 중 오류: {type(e).__name__}: {e}", exc_info=True)
                if isinstance(e, (ConnectionResetError, BrokenPipeError)):
                    is_connected = False
                    break
    
    except asyncio.CancelledError:
        logger.info(f"[{client_info}] WebSocket 핸들러 태스크 취소됨")
    except Exception as e:
        logger.error(f"[{client_info}] WebSocket 핸들러 중 오류: {e}", exc_info=True)
    finally:
        # 연결 상태 업데이트
        is_connected = False
        
        # STT 태스크 취소
        if stt_task and not stt_task.done():
            stt_task.cancel()
            try:
                await stt_task
            except asyncio.CancelledError:
                pass
            except Exception as e:
                logger.warning(f"[{client_info}] STT 태스크 취소 중 오류: {e}")
        
        # LLM/TTS 태스크 취소 (세트의 복사본을 순회)
        tasks_to_cancel = list(llm_tts_tasks)  # 세트를 리스트로 복사
        for task in tasks_to_cancel:
            if not task.done():
                task.cancel()
                try:
                    await task
                except asyncio.CancelledError:
                    pass
                except Exception as e:
                    logger.warning(f"[{client_info}] LLM/TTS 태스크 취소 중 오류: {e}")
        
        llm_tts_tasks.clear()  # 모든 태스크 제거
        
        # 오디오 큐는 메모리 누수 방지를 위해 정리하지만, 데이터 자체는 삭제하지 않음
        # 재연결 시 큐가 유지되므로 데이터 손실 없음
        
        # 사용자 채팅 세션 정리
        try:
            clear_user_session(user_id)
            logger.info(f"[{client_info}] 사용자 채팅 세션 정리 완료 (사용자 ID: {user_id})")
        except Exception as e:
            logger.warning(f"[{client_info}] 사용자 채팅 세션 정리 중 오류: {e}")
        
        # WebSocket 연결 종료
        if websocket.client_state == WebSocketState.CONNECTED:
            try:
                await websocket.close()
                logger.info(f"[{client_info}] WebSocket 연결 종료됨")
            except Exception as e:
                logger.warning(f"[{client_info}] WebSocket 연결 종료 중 오류: {e}")
        
        logger.info(f"[{client_info}] WebSocket 핸들러 정리 완료")
