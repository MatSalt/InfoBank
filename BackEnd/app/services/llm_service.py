# backend/app/services/llm_service.py
import logging
import asyncio
from google import genai
# GenerationConfig, SafetySetting 등은 사용하지 않으므로 주석 처리 또는 삭제 가능
# from google.genai.types import GenerationConfig, SafetySetting, HarmCategory
from google.genai.types import HttpOptions # HttpOptions 임포트
from ..core.config import settings # 설정 객체 직접 임포트
from typing import AsyncIterator # AsyncIterator 임포트

# 로거 설정
logger = logging.getLogger(__name__)

# --- API 키 설정 제거 ---
# API 키를 사용하지 않고 ADC (Application Default Credentials) 등 다른 인증 방식 사용 가정

# --- LLM 응답 스트리밍 함수 (비동기 제너레이터로 수정 + 터미널 출력 추가) ---
async def stream_llm_response(text: str, client_info: str = "Unknown Client") -> AsyncIterator[str]:
    """
    주어진 텍스트를 Vertex AI Gemini LLM 채팅 세션에 보내고,
    응답 텍스트 청크를 비동기적으로 생성(yield)하며 터미널에도 출력합니다.

    Args:
        text: LLM에 전달할 사용자 입력 텍스트 (STT 결과).
        client_info: 요청을 보낸 클라이언트 정보 (로깅용).

    Yields:
        str: LLM으로부터 받은 응답 텍스트 청크.
    """
    logger.info(f"[{client_info}] LLM 요청 시작 (Vertex AI - Chats Interface): '{text[:50]}...'")

    client = None # 클라이언트 변수 초기화
    chat_session = None # 채팅 세션 변수 초기화

    try:
        # 1. genai.Client 인스턴스 생성 (Vertex AI 설정 포함)
        client = genai.Client(
            vertexai=True,
            project=settings.GOOGLE_CLOUD_PROJECT_ID,
            location=settings.VERTEX_AI_LOCATION,
            http_options=HttpOptions(api_version="v1") # 필요시 HttpOptions 유지
        )
        logger.debug(f"[{client_info}] genai.Client 생성 완료 (Vertex AI: project={settings.GOOGLE_CLOUD_PROJECT_ID}, location={settings.VERTEX_AI_LOCATION}).")

        # 2. 채팅 세션 생성
        model_name = settings.GEMINI_MODEL
        chat_session = client.chats.create(model=model_name)
        logger.debug(f"[{client_info}] Gemini Chat Resource 생성 시도 완료 (Model: {model_name}, Target: Vertex AI via chats interface)")

        # 3. 스트리밍 응답 생성 요청 (동기 함수를 별도 스레드에서 실행)
        def send_message_sync():
            # generation_config, safety_settings 등은 필요시 추가 가능
            return chat_session.send_message_stream(text)

        # 동기 스트림을 비동기적으로 처리하기 위한 래퍼
        response_stream = await asyncio.to_thread(send_message_sync)

        # 4. 스트리밍 응답 처리 및 텍스트 청크 생성(yield) 및 터미널 출력
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
        # 리소스 정리 (필요한 경우)
        # chat_session이나 client 관련 정리 로직 추가 가능

