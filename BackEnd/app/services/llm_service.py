# backend/app/services/llm_service.py
import logging
import asyncio
from google import genai
# GenerationConfig, SafetySetting 등은 사용하지 않으므로 주석 처리 또는 삭제 가능
# from google.genai.types import GenerationConfig, SafetySetting, HarmCategory
from google.genai.types import HttpOptions # HttpOptions 임포트
from ..core.config import settings # 설정 객체 직접 임포트

# 로거 설정
logger = logging.getLogger(__name__)

# --- API 키 설정 제거 ---
# API 키를 사용하지 않고 ADC (Application Default Credentials) 등 다른 인증 방식 사용 가정

# --- LLM 응답 스트리밍 함수 (사용자 지정 방식 적용) ---
async def stream_llm_response(text: str, client_info: str = "Unknown Client"):
    """
    주어진 텍스트를 Vertex AI Gemini LLM 채팅 세션에 보내고, 응답을 스트리밍하여 터미널에 출력합니다.
    Vertex AI 설정을 사용하고, client.chats.create() 인터페이스를 사용합니다.

    Args:
        text: LLM에 전달할 사용자 입력 텍스트 (STT 결과).
        client_info: 요청을 보낸 클라이언트 정보 (로깅용).
    """
    logger.info(f"[{client_info}] LLM 요청 시작 (Vertex AI - Chats Interface): '{text[:50]}...'")
    print(f"\n--- [{client_info}] LLM 응답 시작 (Vertex AI - Chats Interface) ---")

    try:
        # 1. genai.Client 인스턴스 생성 (Vertex AI 설정 포함)
        #    이 부분이 Vertex AI를 사용하도록 SDK를 구성하는 핵심입니다.
        client = genai.Client(
            vertexai=True,                           # Vertex AI 사용 명시
            project=settings.GOOGLE_CLOUD_PROJECT_ID, # 설정에서 프로젝트 ID 가져오기
            location=settings.VERTEX_AI_LOCATION,     # 설정에서 리전 가져오기
            http_options=HttpOptions(api_version="v1") # 필요시 HttpOptions 유지
        )
        logger.debug(f"[{client_info}] genai.Client 생성 완료 (Vertex AI: project={settings.GOOGLE_CLOUD_PROJECT_ID}, location={settings.VERTEX_AI_LOCATION}).")

        # 2. 채팅 세션 생성 (원래 코드 방식인 client.chats.create 사용)
        model_name = settings.GEMINI_MODEL
        # Vertex AI 백엔드를 사용하도록 설정된 client 객체에서 chats.create 호출 시도
        chat_session = client.chats.create(model=model_name)
        logger.debug(f"[{client_info}] Gemini Chat Resource 생성 시도 완료 (Model: {model_name}, Target: Vertex AI via chats interface)")

        # 3. 스트리밍 응답 생성 요청 (원래 코드 방식인 send_message_stream 사용)
        def send_message_sync():
            # generation_config, safety_settings 등은 필요시 추가 가능
            return chat_session.send_message_stream(text)

        response_stream = await asyncio.to_thread(send_message_sync)

        # 4. 스트리밍 응답 처리
        full_response_text = ""
        def process_stream():
            nonlocal full_response_text
            for chunk in response_stream:
                # chats 인터페이스는 보통 chunk.text 속성을 가집니다.
                if hasattr(chunk, 'text') and chunk.text:
                    print(chunk.text, end="", flush=True) # 터미널에 실시간 출력
                    full_response_text += chunk.text
                else:
                    # 예상치 못한 청크 구조 로깅 (디버깅 시 필요할 수 있음)
                    # logger.debug(f"[{client_info}] Received chunk without text or empty text: {chunk}")
                    pass # 혹은 다른 처리

        await asyncio.to_thread(process_stream) # 동기 루프를 별도 스레드에서 실행

        print("\n--- LLM 응답 종료 (Vertex AI - Chats Interface) ---")
        logger.info(f"[{client_info}] LLM 응답 스트리밍 완료 (Vertex AI - Chats Interface). 총 길이: {len(full_response_text)}")

    except AttributeError as e:
        # client.chats 또는 chat_session.send_message_stream 관련 속성 오류 발생 시
        logger.error(f"[{client_info}] LLM 오류: 객체 속성 오류. Vertex AI 설정 시 'client.chats' 또는 'send_message_stream' 인터페이스가 지원되지 않을 수 있습니다. 오류: {e}", exc_info=True)
        print(f"\n--- LLM 오류 발생: 객체 속성 오류 ({e}) ---")
        # 사용자에게 대안 제시
        if "chats" in str(e).lower() or "send_message_stream" in str(e).lower():
             print("\n참고: Vertex AI 사용 시 'client.get_generative_model()' 및 'model.generate_content(stream=True)' 방식 사용이 권장될 수 있습니다.")
             logger.info("Vertex AI 권장 방식: client.get_generative_model() / model.generate_content(stream=True)")
    except asyncio.CancelledError:
        logger.warning(f"[{client_info}] LLM 스트리밍 작업 취소됨 (Vertex AI - Chats Interface).")
        print("\n--- LLM 응답 취소됨 ---")
    except Exception as e:
        # 인증, API 엔드포인트, 할당량 등 다양한 오류 가능성 포함
        logger.error(f"[{client_info}] LLM 스트리밍 중 오류 발생 (Vertex AI - Chats Interface): {e}", exc_info=True)
        print(f"\n--- LLM 오류 발생: {e} ---")

