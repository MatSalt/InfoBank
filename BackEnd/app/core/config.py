from pydantic_settings import BaseSettings
from typing import List
import os
from dotenv import load_dotenv

# .env 파일로부터 환경 변수 로드
load_dotenv()

class Settings(BaseSettings):
    # 서버 설정
    SERVER_HOST: str = os.getenv("SERVER_HOST", "0.0.0.0") # 서버 호스트 주소
    SERVER_PORT: int = int(os.getenv("PORT", "8080")) # 서버 포트 (PORT 환경 변수 사용)
    
    # CORS 설정 - 모든 오리진 허용
    ALLOWED_ORIGINS: List[str] = os.getenv("ALLOWED_ORIGINS", "*").split(",")

    # Google Cloud 설정
    GOOGLE_CLOUD_PROJECT_ID: str = os.getenv("GOOGLE_CLOUD_PROJECT_ID", "civil-hull-456308-c4") # 기본값 제거, 필수 설정으로 변경

    # STT (Speech-to-Text) 설정
    STT_SAMPLE_RATE: int = int(os.getenv("STT_SAMPLE_RATE", "16000")) # 오디오 샘플링 레이트 (Hz)
    STT_LANGUAGE_CODES: List[str] = os.getenv("STT_LANGUAGE_CODES", "en-US,ko-KR").split(",") # 인식할 언어 코드 목록 (BCP-47 형식)
    STT_MODEL: str = os.getenv("STT_MODEL", "telephony") # 사용할 STT 모델

    # --- LLM (Gemini) 관련 설정 ---
    GEMINI_MODEL: str = os.getenv("GEMINI_MODEL", "gemini-1.5-flash-002") # Vertex AI에서 사용 가능한 모델 확인 필요
    USE_VERTEX_AI: bool = os.getenv("USE_VERTEX_AI", "True").lower() == "true" # 기본값은 True로 설정
    VERTEX_AI_LOCATION: str = os.getenv("VERTEX_AI_LOCATION", "asia-northeast3") # Vertex AI 리전 설정
    SYSTEM_INSTRUCTION: str = os.getenv("SYSTEM_INSTRUCTION", "당신은 친절하고 도움이 되는 음성 비서입니다. 당신의 응답은 간결하고, 대화체이며, 소리 내어 읽었을 때 이해하기 쉬워야 합니다. 사용자의 질문에 직접적이고 짧게 답변하세요. 불필요한 전문 용어나 지나치게 격식적인 언어는 피하세요. 명시적으로 더 자세한 정보가 요청되지 않는 한, 응답을 1-2 문장으로 제한하세요. 최대한 빨리 대답해 주세요.") # .env 파일에서 시스템 지시문 로드

    # --- TTS (Text-to-Speech) 설정 추가 ---
    TTS_VOICE_NAME: str = os.getenv("TTS_VOICE_NAME", "ko-KR-Chirp3-HD-Aoede") # 사용할 TTS 음성 이름 (예: ko-KR-Standard-A, ko-KR-Wavenet-A)
    TTS_LANGUAGE_CODE: str = os.getenv("TTS_LANGUAGE_CODE", "ko-KR") # 사용할 TTS 언어 코드

    class Config:
        # .env 파일이 존재하면 로드
        env_file = ".env"
        env_file_encoding = 'utf-8' # 인코딩 설정
        extra = "allow"  # 추가 필드 허용

# 설정 객체 인스턴스 생성
settings = Settings()

# 필수 환경 변수 확인 (GCP Project ID)
if not settings.GOOGLE_CLOUD_PROJECT_ID:
    raise ValueError("GOOGLE_CLOUD_PROJECT_ID가 설정되지 않았습니다. 환경 변수나 .env 파일에 설정해주세요.")
# --- Vertex AI 리전 확인 추가 ---
if not settings.VERTEX_AI_LOCATION:
    raise ValueError("VERTEX_AI_LOCATION이 설정되지 않았습니다. 환경 변수나 .env 파일에 설정해주세요.")
# --- TTS 설정 확인 추가 ---
if not settings.TTS_VOICE_NAME:
    raise ValueError("TTS_VOICE_NAME이 설정되지 않았습니다. 환경 변수나 .env 파일에 설정해주세요.")
if not settings.TTS_LANGUAGE_CODE:
    raise ValueError("TTS_LANGUAGE_CODE가 설정되지 않았습니다. 환경 변수나 .env 파일에 설정해주세요.") 