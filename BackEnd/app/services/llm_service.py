# backend/app/services/llm_service.py
import logging
import asyncio
import google.generativeai as genai
# GenerationConfig, SafetySetting 등은 사용하지 않으므로 주석 처리 또는 삭제 가능
# from google.generativeai.types import GenerationConfig, SafetySetting, HarmCategory
from google.generativeai.types import HttpOptions # HttpOptions 임포트
from ..core.config import settings # 설정 가져오기 (필요시 다른 설정 사용 가능)

# 로거 설정
logger = logging.getLogger(__name__)

# --- API 키 설정 제거 ---
# API 키를 사용하지 않고 ADC (Application Default Credentials) 등 다른 인증 방식 사용 가정

# --- LLM 응답 스트리밍 함수 (사용자 지정 방식 적용) ---
async def stream_llm_response(text: str, client_info: str = "Unknown Client"):
    """
    주어진 텍스트를 Gemini LLM 채팅 세션에 보내고, 응답을 스트리밍하여 터미널에 출력합니다.
    사용자 지정 방식(HttpOptions, chats.create, send_message_stream)을 사용합니다.

    Args:
        text: LLM에 전달할 사용자 입력 텍스트 (STT 결과).
        client_info: 요청을 보낸 클라이언트 정보 (로깅용).
    """
    logger.info(f"[{client_info}] LLM 요청 시작 (Custom Method): '{text[:50]}...'")
    print(f"\n--- [{client_info}] LLM 응답 시작 ---")

    # GenerationConfig 및 SafetySettings 정의 제거 (사용자 예시에 없음)

    try:
        # 1. genai.Client 인스턴스 생성 (HttpOptions 사용, API 키 설정 없음)
        client = genai.Client(http_options=HttpOptions(api_version="v1"))
        logger.debug(f"[{client_info}] genai.Client 생성 완료 (HttpOptions 사용).")

        # 2. 채팅 세션 생성 (client.chats.create 사용, 환경변수에서 모델 이름 가져오기)
        model_name = settings.GEMINI_MODEL
        chat_session = client.chats.create(model=model_name)
        logger.debug(f"[{client_info}] Gemini Chat Resource 생성 완료 (Model: {model_name})")

        # 3. 스트리밍 응답 생성 요청 (동기 함수이므로 asyncio.to_thread 사용)
        # 사용자 예시에 따라 send_message_stream 사용
        def send_message_sync():
            # generation_config, safety_settings 등 추가 파라미터 제거
            return chat_session.send_message_stream(text)

        response_stream = await asyncio.to_thread(send_message_sync)

        # 4. 스트리밍 응답 처리 (동기 루프, 사용자 예시 형식)
        full_response_text = ""
        def process_stream():
            nonlocal full_response_text
            # 사용자 예시와 동일한 반복 및 출력 방식 사용
            for chunk in response_stream:
                if hasattr(chunk, 'text') and chunk.text: # chunk에 text 속성이 있는지 확인
                    print(chunk.text, end="", flush=True) # 터미널에 실시간 출력
                    full_response_text += chunk.text
                # 필요시 다른 chunk 속성 확인 (예: chunk.candidates)
                # logger.debug(f"Chunk received: {chunk}") # 전체 청크 내용 로깅

        await asyncio.to_thread(process_stream) # 동기 루프를 별도 스레드에서 실행

        print("\n--- LLM 응답 종료 ---")
        logger.info(f"[{client_info}] LLM 응답 스트리밍 완료 (Custom Method). 총 길이: {len(full_response_text)}")

    except AttributeError as e:
         logger.error(f"[{client_info}] LLM 오류: 객체 속성 오류. 'send_message_stream' 또는 관련 속성이 없을 수 있습니다. 오류: {e}", exc_info=True)
         print(f"\n--- LLM 오류 발생: 객체 속성 오류 ({e}) ---")
    except asyncio.CancelledError:
        logger.warning(f"[{client_info}] LLM 스트리밍 작업 취소됨 (Custom Method).")
        print("\n--- LLM 응답 취소됨 ---")
    except Exception as e:
        # 인증 실패 등 다양한 오류 가능성 포함
        logger.error(f"[{client_info}] LLM 스트리밍 중 오류 발생 (Custom Method): {e}", exc_info=True)
        print(f"\n--- LLM 오류 발생: {e} ---")

