"""
WebSocket 유틸리티 모듈.

이 모듈은 WebSocket 관련 유틸리티 기능을 제공합니다.
"""
import logging
import asyncio
from typing import Set, Dict, Any, List
from fastapi import WebSocket
from starlette.websockets import WebSocketState

# 로거 설정
logger = logging.getLogger(__name__)

async def send_json_message(
    websocket: WebSocket, 
    message: Dict[str, Any], 
    client_id: str, 
    error_msg: str = "메시지 전송 중 오류"
) -> bool:
    """
    WebSocket을 통해 JSON 메시지를 안전하게 전송합니다.
    
    Args:
        websocket: WebSocket 연결 객체
        message: 전송할 JSON 메시지
        client_id: 클라이언트 식별자(로깅용)
        error_msg: 오류 발생 시 로그에 기록할 메시지
        
    Returns:
        bool: 메시지 전송 성공 여부
    """
    try:
        if websocket.client_state == WebSocketState.CONNECTED:
            await websocket.send_json(message)
            return True
    except Exception as e:
        logger.error(f"[{client_id}] {error_msg}: {e}")
    
    return False

async def handle_interruption(
    websocket: WebSocket,
    client_id: str,
    is_connected: bool,
    tasks: Set[asyncio.Task]
) -> None:
    """
    사용자 인터럽션 발생 시 현재 태스크를 취소하고 정리합니다.
    
    Args:
        websocket: WebSocket 연결 객체
        client_id: 클라이언트 식별자(로깅용)
        is_connected: 연결 상태 플래그
        tasks: 취소할 태스크 세트
        
    Returns:
        None
    """
    logger.info(f"[{client_id}] 인터럽션 처리 시작: {len(tasks)}개 태스크 취소")
    
    # 현재 태스크 취소 및 정리
    tasks_to_cancel = list(tasks)
    for task in tasks_to_cancel:
        if not task.done():
            task.cancel()
            try:
                await task
            except asyncio.CancelledError:
                logger.debug(f"[{client_id}] 인터럽션으로 태스크 취소됨")
            except Exception as e:
                logger.warning(f"[{client_id}] 인터럽션 처리 중 태스크 취소 오류: {e}")
    
    tasks.clear()  # 모든 태스크 제거
    
    # 사용자에게 마이크 활성화 메시지 전송
    if is_connected and websocket.client_state == WebSocketState.CONNECTED:
        await send_json_message(
            websocket,
            {
                "control": "response_status",
                "action": "end_processing",
                "reason": "interruption",
                "message": "AI 응답이 중단되었습니다. 계속 말씀하세요."
            },
            client_id,
            "인터럽션 후 응답 처리 종료 메시지 전송 중 오류"
        )
        logger.debug(f"[{client_id}] 인터럽션 후 응답 처리 종료 신호 전송")
    
    logger.info(f"[{client_id}] 인터럽션 처리 완료") 