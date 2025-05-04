# backend/app/routers/voice.py
import logging
import asyncio
import re # 정규식 임포트 (현재 로직에서는 필수는 아니지만 향후 사용을 위해)
import uuid # 사용자 ID 생성을 위한 UUID 모듈 추가
from fastapi import APIRouter, WebSocket, WebSocketDisconnect
from starlette.websockets import WebSocketState
from app.services.stt_service import handle_stt_stream, STTTimeoutError
from app.services.llm_service import stream_llm_response, clear_user_session # clear_user_session 함수 추가
from app.services.tts_service import synthesize_speech_stream # 업데이트된 TTS 서비스 임포트
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

# --- 텍스트 청킹을 위한 헬퍼 함수 ---
async def chunk_text_by_punctuation(
    llm_stream: AsyncIterator[str],
    min_length: int = 10, # 최소 길이를 약간 증가
    punctuation: str = '.?!,' # 구두점으로 분할
) -> AsyncIterator[str]:
    """
    LLM 텍스트 스트림을 비동기적으로 소비하고, 텍스트를 누적하여
    구두점이나 최소 길이로 분할된 청크를 생성하여 더 자연스러운 TTS 입력을 제공합니다.
    상위 오류를 적절히 처리합니다.

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
         logger.error(f"텍스트 청커 생성기 내부 오류: {e}", exc_info=True)
         raise # 호출자에게 다시 발생시킴


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

    # --- LLM, 텍스트 청킹, TTS 처리 함수 ---
    async def handle_llm_and_tts(transcript: str, ws: WebSocket, client_id: str):
        """LLM 응답을 받아 자연스럽게 청킹하고, TTS로 변환하여 WebSocket으로 오디오 청크를 전송합니다."""
        nonlocal is_connected
        logger.info(f"[{client_id}] LLM->청커->TTS 파이프라인 시작: '{transcript[:50]}...'")
        
        try:
            # LLM 호출 직전에 마이크 비활성화 요청 전송
            if is_connected and ws.client_state == WebSocketState.CONNECTED:
                await ws.send_json({
                    "control": "mic_status",
                    "action": "disable",
                    "reason": "processing",
                    "message": "AI가 응답 중입니다..."
                })
                logger.debug(f"[{client_id}] LLM 처리를 위한 마이크 비활성화 요청 전송")
            
            # 기존 LLM 및 TTS 스트리밍 로직
            llm_stream = stream_llm_response(transcript, client_id, user_id)
            processed_text_stream = chunk_text_by_punctuation(llm_stream)
            tts_stream = synthesize_speech_stream(processed_text_stream)
            
            # TTS 오디오 전송 시작 시간 기록
            tts_start_time = time.time()
            audio_chunks_sent = 0
            
            # TTS 오디오 청크 전송
            async for audio_chunk in tts_stream:
                if not is_connected:
                    break
                
                if ws.client_state == WebSocketState.CONNECTED:
                    await ws.send_bytes(audio_chunk)
                    audio_chunks_sent += 1
            
            # 오디오 전송 완료 시간 기록
            tts_end_time = time.time()
            tts_duration = tts_end_time - tts_start_time
            logger.info(f"[{client_id}] TTS 오디오 전송 완료: {audio_chunks_sent}개 청크, {tts_duration:.2f}초 소요")
            
            # 마지막 오디오 청크가 클라이언트에서 재생될 시간 고려 (평균 오디오 청크 길이 대략 0.5초로 가정)
            estimated_playback_time = 0.5  # 마지막 청크의 재생 시간 예상치 (초)
            
            # TTS 전송 완료 후 마이크 활성화 요청 전송
            if is_connected and ws.client_state == WebSocketState.CONNECTED:
                await ws.send_json({
                    "control": "mic_status",
                    "action": "enable",
                    "reason": "processing_complete",
                    "message": "AI 응답이 완료되었습니다. 대화를 계속하세요.",
                    "audioInfo": {
                        "chunksSent": audio_chunks_sent,
                        "estimatedDuration": tts_duration
                    }
                })
                logger.debug(f"[{client_id}] TTS 재생 완료를 위한 마이크 활성화 요청 전송")
        
        except Exception as e:
            logger.error(f"[{client_id}] TTS 스트림 처리 중 오류: {e}", exc_info=True)
            # 오류 발생 시에도 마이크 활성화 요청 전송
            if is_connected and ws.client_state == WebSocketState.CONNECTED:
                try:
                    await ws.send_json({
                        "control": "mic_status",
                        "action": "enable",
                        "reason": "error",
                        "message": "오류가 발생했습니다. 다시 시도해주세요."
                    })
                except Exception as send_err:
                    logger.error(f"[{client_id}] 오류 후 마이크 활성화 메시지 전송 중 추가 오류: {send_err}")

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
                    await handle_interruption()
                return  # 인터럽션 처리 후 종료
            
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
        task = asyncio.create_task(handle_llm_and_tts(transcript, websocket, client_info))
        llm_tts_tasks.add(task)
        
        # 태스크 완료 시 집합에서 제거
        task.add_done_callback(lambda t: llm_tts_tasks.discard(t))

    # --- 인터럽션 처리 함수 ---
    async def handle_interruption():
        """사용자 인터럽션 발생 시 현재 LLM/TTS 태스크를 취소하고 정리합니다."""
        nonlocal llm_tts_tasks
        
        logger.info(f"[{client_info}] 인터럽션 처리 시작: {len(llm_tts_tasks)}개 태스크 취소")
        
        # 현재 LLM/TTS 태스크 취소 및 정리
        tasks_to_cancel = list(llm_tts_tasks)
        for task in tasks_to_cancel:
            if not task.done():
                task.cancel()
                try:
                    await task
                except asyncio.CancelledError:
                    logger.debug(f"[{client_info}] 인터럽션으로 태스크 취소됨")
                except Exception as e:
                    logger.warning(f"[{client_info}] 인터럽션 처리 중 태스크 취소 오류: {e}")
        
        llm_tts_tasks.clear()  # 모든 태스크 제거
        
        # 사용자에게 마이크 활성화 메시지 전송
        if is_connected and websocket.client_state == WebSocketState.CONNECTED:
            try:
                await websocket.send_json({
                    "control": "mic_status",
                    "action": "enable",
                    "reason": "interruption",
                    "message": "AI 응답이 중단되었습니다. 계속 말씀하세요."
                })
                logger.debug(f"[{client_info}] 인터럽션 후 마이크 활성화 요청 전송")
            except Exception as e:
                logger.error(f"[{client_info}] 인터럽션 후 마이크 활성화 메시지 전송 중 오류: {e}")
        
        logger.info(f"[{client_info}] 인터럽션 처리 완료")

    # --- 메인 루프: STT 관리 및 메시지 수신 ---
    try:
        # STT 태스크 시작
        stt_task = asyncio.create_task(handle_stt_stream(audio_queue, process_stt_result))
        
        # 메시지 수신 루프
        while is_connected:
            try:
                # 타임아웃 설정으로 무한 대기 방지
                data = await asyncio.wait_for(websocket.receive_bytes(), timeout=30.0)
                
                # 연결 상태 확인
                if not is_connected or websocket.client_state != WebSocketState.CONNECTED:
                    logger.warning(f"[{client_info}] 연결이 끊어진 상태에서 데이터 수신. 루프 종료.")
                    break
                
                # 오디오 데이터를 큐에 추가
                await audio_queue.put(data)
                logger.debug(f"[{client_info}] 오디오 데이터 수신 및 큐에 추가됨 ({len(data)} bytes)")
                
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
                logger.error(f"[{client_info}] 메시지 수신 중 오류: {e}", exc_info=True)
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
        
        # LLM/TTS 태스크 취소
        for task in llm_tts_tasks:
            if not task.done():
                task.cancel()
                try:
                    await task
                except asyncio.CancelledError:
                    pass
                except Exception as e:
                    logger.warning(f"[{client_info}] LLM/TTS 태스크 취소 중 오류: {e}")
        
        # 오디오 큐 정리
        while not audio_queue.empty():
            try:
                audio_queue.get_nowait()
            except asyncio.QueueEmpty:
                break
        
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
