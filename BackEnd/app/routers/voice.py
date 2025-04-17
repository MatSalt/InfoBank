# backend/app/routers/voice.py
import logging
from fastapi import APIRouter, WebSocket, WebSocketDisconnect

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
    WebSocket 연결을 처리하고 오디오 데이터를 수신하는 엔드포인트입니다.

    Args:
        websocket (WebSocket): 클라이언트와의 WebSocket 연결 객체.
    """
    await websocket.accept()
    client_host = websocket.client.host
    client_port = websocket.client.port
    logger.info(f"WebSocket connection accepted from: {client_host}:{client_port}")
    try:
        while True:
            # 클라이언트로부터 메시지 수신 대기
            data = await websocket.receive()

            if "bytes" in data:
                audio_chunk = data["bytes"]
                # 오디오 데이터(bytes) 수신 확인 로그
                logger.info(f"Received audio chunk: {len(audio_chunk)} bytes from {client_host}:{client_port}")
                # TODO: 여기에 수신된 audio_chunk를 처리하는 서비스 로직 호출
                # (예: services.voice_service.process_audio(audio_chunk))

            elif "text" in data:
                # 텍스트 메시지 수신 (예: 연결 종료 신호 등)
                text_data = data["text"]
                logger.info(f"Received text message: {text_data} from {client_host}:{client_port}")
                if text_data == "Client stopped recording":
                    logger.info(f"Client {client_host}:{client_port} indicated recording stopped.")
                    # 필요시 추가 처리 후 루프 종료 또는 유지
                    # break

            # 필요에 따라 클라이언트로 메시지 전송 가능
            # await websocket.send_json({"status": "received", "bytes": len(audio_chunk)})

    except WebSocketDisconnect as e:
        logger.warning(f"WebSocket disconnected: {client_host}:{client_port} - Code: {e.code}, Reason: {e.reason}")
        # 클라이언트 연결 종료 시 처리 로직
    except Exception as e:
        logger.error(f"An error occurred in WebSocket connection with {client_host}:{client_port}: {e}", exc_info=True)
        # 오류 발생 시 연결 종료 (오류 코드 및 이유 명시 가능)
        await websocket.close(code=1011, reason=f"Server error: {e}")
    finally:
        # 연결이 정상적으로 또는 예외로 인해 종료될 때 실행
        logger.info(f"WebSocket connection closed for: {client_host}:{client_port}")
        # 필요한 경우 리소스 정리 등 수행
