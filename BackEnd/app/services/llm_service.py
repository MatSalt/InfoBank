# backend/app/services/llm_service.py
import logging
import asyncio
from google import genai
# GenerationConfig, SafetySetting 등은 사용하지 않으므로 주석 처리 또는 삭제 가능
# from google.genai.types import GenerationConfig, SafetySetting, HarmCategory
from google.genai.types import HttpOptions # HttpOptions 임포트
from ..core.config import settings # 설정 객체 직접 임포트
from typing import AsyncIterator, Dict, Optional, Any # 타입 힌트 추가

# 세션 관리자 임포트
from .session_manager import chat_session_manager

# RAG 서비스 임포트
from .rag_service import rag_service

# 로거 설정
logger = logging.getLogger(__name__)

# --- LLM 응답 스트리밍 함수 (비동기 제너레이터로 수정 + 터미널 출력 추가) ---
async def stream_llm_response(
    text: str, 
    client_info: str = "Unknown Client",
    user_id: Optional[str] = None,
    new_session: bool = False
) -> AsyncIterator[str]:
    """
    주어진 텍스트를 LLM에 전송하고 응답을 스트리밍합니다.
    RAG 서비스를 기본으로 사용하며, 오류 시 기본 에러 메시지를 반환합니다.

    Args:
        text: LLM에 전달할 사용자 입력 텍스트 (STT 결과).
        client_info: 요청을 보낸 클라이언트 정보 (로깅용).
        user_id: 사용자 식별자 (채팅 세션 관리용).
        new_session: 새로운 채팅 세션을 시작할지 여부.

    Yields:
        str: LLM으로부터 받은 응답 텍스트 청크.
    """
    # 사용자 ID가 제공되지 않으면 클라이언트 정보를 기반으로 생성
    if user_id is None:
        user_id = client_info
    
    logger.info(f"[{client_info}] LLM 요청 시작: '{text[:50]}...'")
    
    # 새 세션 요청이면 기존 세션 초기화
    if new_session:
        chat_session_manager.clear_session(user_id)
        logger.debug(f"[{client_info}] 새 채팅 세션 시작 (사용자: {user_id})")
    
    try:
        # RAG 서비스 초기화 (아직 안 했다면)
        if not rag_service.initialized:
            rag_service.initialize()
        
        # RAG 서비스를 통한 처리
        print(f"\n--- [{client_info}] LLM 응답 시작 ---", flush=True)
        
        async for text_chunk in rag_service.process_query(text, client_info):
            # 터미널에 즉시 출력 (디버깅용)
            print(text_chunk, end="", flush=True)
            yield text_chunk
            
        print(f"\n--- [{client_info}] LLM 응답 종료 ---", flush=True)
        
    except Exception as e:
        logger.error(f"[{client_info}] LLM 처리 중 오류 발생: {e}", exc_info=True)
        error_message = "죄송합니다. 요청을 처리하는 중에 오류가 발생했습니다. 잠시 후 다시 시도해주세요."
        print(f"\n--- [{client_info}] 오류 발생: {e} ---", flush=True)
        yield error_message
    finally:
        logger.debug(f"[{client_info}] LLM 스트리밍 함수 종료.")

# --- 채팅 세션 관리 함수 ---
def clear_user_session(user_id: str) -> None:
    """
    특정 사용자의 채팅 세션을 초기화합니다.
    
    Args:
        user_id: 사용자 식별자
    """
    chat_session_manager.clear_session(user_id)
    logger.info(f"사용자 채팅 세션 초기화 완료: {user_id}")

def clear_all_sessions() -> None:
    """
    모든 사용자의 채팅 세션을 초기화합니다.
    """
    chat_session_manager.clear_all_sessions()
    logger.info("모든 사용자 채팅 세션 초기화 완료")

