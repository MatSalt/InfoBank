# backend/app/routers/voice.py
import logging
import asyncio
from fastapi import APIRouter, WebSocket, WebSocketDisconnect
from app.services.stt_service import handle_stt_stream # STT 서비스 함수 임포트

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
    WebSocket 연결을 처리하고, 오디오를 수신하여 STT 서비스로 전달하고, 결과를 처리합니다.
    향후 LLM, TTS 서비스와 연동될 수 있습니다.
    """
    await websocket.accept() # 클라이언트의 웹소켓 연결 요청 수락
    client_host = websocket.client.host
    client_port = websocket.client.port
    client_info = f"{client_host}:{client_port}"
    logger.info(f"WebSocket 연결 수락됨: {client_info}")

    audio_queue = asyncio.Queue() # 오디오 청크를 담을 비동기 큐
    stt_task = None # STT 처리 태스크

    # --- STT 결과 처리 콜백 함수 ---
    async def process_stt_result(transcript: str, is_final: bool):
        """STT 결과를 로그로 남기거나 클라이언트에게 전송하는 콜백 함수"""
        if not is_final:
            logger.debug(f"[{client_info}] 중간 결과: {transcript}")
        else:
            logger.info(f"[{client_info}] 최종 결과: {transcript}")
            # 여기에 최종 결과를 LLM 서비스로 보내거나,
            # TTS 서비스로 보내 음성으로 변환 후 클라이언트에게 전송하는 로직 추가 가능
            # 예시: await websocket.send_text(f"인식 결과: {transcript}")

    try:
        # --- STT 서비스 시작 ---
        # 별도의 태스크에서 STT 스트리밍 처리 시작
        stt_task = asyncio.create_task(
            handle_stt_stream(audio_queue, process_stt_result)
        )
        logger.info(f"[{client_info}] STT 서비스 태스크 시작됨.")

        # --- 클라이언트로부터 오디오 수신 ---
        while True:
            data = await websocket.receive() # 클라이언트로부터 메시지 수신 대기

            if "bytes" in data: # 수신된 데이터가 오디오 청크(bytes)인 경우
                audio_chunk = data["bytes"]
                # 오디오 청크를 STT 서비스가 사용할 큐에 넣음
                await audio_queue.put(audio_chunk)

            elif "text" in data: # 수신된 데이터가 텍스트인 경우
                text_data = data["text"]
                logger.info(f"텍스트 메시지 수신: {text_data} from {client_info}")
                # 클라이언트가 녹음 중지 또는 연결 종료 신호를 보낸 경우 처리
                if text_data == "Client stopped recording" or text_data == "disconnect":
                    logger.info(f"클라이언트 {client_info}가 중지 신호 보냄. 스트림 종료 중.")
                    break # 오디오 수신 루프 종료

    except WebSocketDisconnect as e: # 웹소켓 연결이 끊어진 경우
        logger.warning(f"WebSocket 연결 끊김: {client_info} - 코드: {e.code}, 이유: {e.reason}")
    except Exception as e: # 그 외 예외 발생 시
        logger.error(f"WebSocket 연결 중 오류 발생 ({client_info}): {e}", exc_info=True)
        # 서버 오류 시 웹소켓 연결을 정상적으로 닫으려고 시도
        try:
            await websocket.close(code=1011, reason=f"서버 오류: {e}")
        except Exception:
            pass # 이미 닫혔을 수 있음
    finally: # 연결 종료 또는 예외 발생 시 항상 실행
        logger.info(f"[{client_info}] WebSocket 연결 정리 중...")

        # STT 서비스에게 오디오 전송 중단 신호 보내기
        if audio_queue:
             await audio_queue.put(None) # 제너레이터를 중지시키기 위한 None 값(Sentinel) 전송

        # STT 처리 태스크 취소 및 대기
        if stt_task and not stt_task.done():
            logger.info(f"[{client_info}] STT 서비스 태스크 취소 중...")
            stt_task.cancel() # 태스크 취소 요청
            try:
                await stt_task # 태스크가 완전히 종료될 때까지 대기
            except asyncio.CancelledError:
                logger.info(f"[{client_info}] STT 서비스 태스크 성공적으로 취소됨.")
            except Exception as e:
                 logger.error(f"[{client_info}] STT 태스크 종료 대기 중 오류 발생: {e}", exc_info=True)

        # 웹소켓이 아직 닫히지 않았다면 닫기 시도
        try:
            # 닫기 전에 상태 확인
             if websocket.client_state == websocket.client_state.CONNECTED or websocket.client_state == websocket.client_state.CONNECTING:
                 await websocket.close()
                 logger.info(f"[{client_info}] WebSocket 연결 명시적으로 닫힘.")
        except Exception as e:
            logger.warning(f"[{client_info}] WebSocket 닫기 오류 (이미 닫혔을 수 있음): {e}")

        logger.info(f"WebSocket 연결 종료됨: {client_info}")
