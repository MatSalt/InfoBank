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
    주어진 텍스트를 Vertex AI Gemini LLM 채팅 세션에 보내고,
    응답 텍스트 청크를 비동기적으로 생성(yield)하며 터미널에도 출력합니다.
    
    RAG 처리 통합: 42서울 관련 키워드가 있으면 RAG 파이프라인을 사용합니다.

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
    
    # RAG 서비스를 통한 처리
    try:
        # RAG 서비스 초기화 (아직 안 했다면)
        if not rag_service.initialized:
            rag_service.initialize()
        
        # RAG 서비스를 통한 처리
        print(f"\n--- [{client_info}] LLM 응답 (RAG 사용) 시작 ---", flush=True) # 터미널 출력 시작 표시
        
        async for text_chunk in rag_service.process_query(text, client_info):
            # 터미널에 즉시 출력 (디버깅용)
            print(text_chunk, end="", flush=True)
            yield text_chunk
            
        print(f"\n--- [{client_info}] LLM 응답 (RAG 사용) 종료 ---", flush=True)
        return
        
    except Exception as e:
        logger.error(f"[{client_info}] RAG 서비스 처리 중 오류 발생: {e}", exc_info=True)
        logger.info(f"[{client_info}] RAG 오류로 인해 기본 LLM 서비스로 폴백")
        print(f"\n--- [{client_info}] RAG 처리 오류, 기본 LLM으로 폴백 ---", flush=True)
        # 오류 발생 시 기본 LLM 호출로 폴백
    
    # 시스템 지시문이 있는지 확인
    system_instruction = settings.SYSTEM_INSTRUCTION
    if system_instruction:
        logger.info(f"[{client_info}] 시스템 지시문 포함: '{system_instruction[:50]}...'")
    
    # 새 세션 요청이면 기존 세션 초기화
    if new_session:
        chat_session_manager.clear_session(user_id)
        logger.debug(f"[{client_info}] 새 채팅 세션 시작 (사용자: {user_id})")
    
    # 채팅 세션 가져오기
    chat_session = chat_session_manager.get_session(user_id)
    
    try:
        # 스트리밍 응답 생성 요청 (동기 함수를 별도 스레드에서 실행)
        def send_message_sync():
            # 시스템 지시문이 있을 경우 텍스트 앞에 추가
            if system_instruction:
                combined_text = f"{system_instruction}\n\nUser: {text}"
                return chat_session.send_message_stream(combined_text)
            else:
                # 기존 방식대로 단순 텍스트만 전달
                return chat_session.send_message_stream(text)

        # 동기 스트림을 비동기적으로 처리하기 위한 래퍼
        response_stream = await asyncio.to_thread(send_message_sync)

        # 스트리밍 응답 처리 및 텍스트 청크 생성(yield) 및 터미널 출력
        logger.info(f"[{client_info}] LLM 응답 스트리밍 시작...")
        print(f"\n--- [{client_info}] LLM 응답 (터미널 출력) 시작 ---", flush=True) # 터미널 출력 시작 표시

        chunk_count = 0
        for chunk in response_stream: # 이 루프는 동기적으로 실행됨
            if hasattr(chunk, 'text') and chunk.text:
                text_chunk = chunk.text
                logger.debug(f"[{client_info}] LLM 텍스트 청크 수신: '{text_chunk[:30]}...'")
                # 터미널에 즉시 출력 (디버깅용)
                print(text_chunk, end="", flush=True)
                yield text_chunk # 텍스트 청크를 생성
                chunk_count += 1
                logger.debug(f"[{client_info}] LLM 텍스트 청크 생성(yield) 완료.")
            else:
                # 예상치 못한 청크 구조 로깅
                # logger.debug(f"[{client_info}] Received chunk without text or empty text: {chunk}")
                pass

        print(f"\n--- [{client_info}] LLM 응답 (터미널 출력) 종료 ---", flush=True) # 터미널 출력 종료 표시
        logger.info(f"[{client_info}] LLM 응답 스트리밍 완료. 총 {chunk_count}개 청크 생성됨.")

    except AttributeError as e:
        logger.error(f"[{client_info}] LLM 오류: 객체 속성 오류. Vertex AI 설정 시 'client.chats' 또는 'send_message_stream' 인터페이스가 지원되지 않을 수 있습니다. 오류: {e}", exc_info=True)
        print(f"\n--- [{client_info}] LLM 오류 발생 (터미널): {e} ---", flush=True) # 오류도 터미널에 출력
        raise
    except asyncio.CancelledError:
        logger.warning(f"[{client_info}] LLM 스트리밍 작업 취소됨 (Vertex AI - Chats Interface).")
        print(f"\n--- [{client_info}] LLM 응답 취소됨 (터미널) ---", flush=True) # 취소도 터미널에 출력
        raise
    except Exception as e:
        logger.error(f"[{client_info}] LLM 스트리밍 중 오류 발생 (Vertex AI - Chats Interface): {e}", exc_info=True)
        print(f"\n--- [{client_info}] LLM 오류 발생 (터미널): {e} ---", flush=True) # 오류도 터미널에 출력
        raise
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

