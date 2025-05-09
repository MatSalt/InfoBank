from pydantic_settings import BaseSettings
from typing import List, Dict
import os
from dotenv import load_dotenv

# .env 파일로부터 환경 변수 로드
load_dotenv()

# 현재 환경 확인
ENVIRONMENT = os.getenv("ENVIRONMENT", "development").lower()

# 기본 CORS 설정 - 환경에 따라 다른 기본값 사용
DEFAULT_ALLOWED_ORIGINS = [
    "http://localhost:5173",  # 로컬 개발 서버 (Vite 기본 포트)
    "http://localhost:3000",  # 로컬 개발 서버 (일반적인 포트)
    "http://127.0.0.1:5173",  # 로컬 IP
    "http://127.0.0.1:3000",  # 로컬 IP
]

class Settings(BaseSettings):
    # 서버 설정
    SERVER_HOST: str = os.getenv("SERVER_HOST", "0.0.0.0") # 서버 호스트 주소
    SERVER_PORT: int = int(os.getenv("PORT", "8080")) # 서버 포트 (PORT 환경 변수 사용)
    
    # CORS 설정 - 특정 도메인만 허용
    # "*"는 모든 오리진을 허용하므로 프로덕션 환경에서는 사용하지 않아야 함
    ALLOWED_ORIGINS: List[str] = os.getenv("ALLOWED_ORIGINS", ",".join(DEFAULT_ALLOWED_ORIGINS)).split(",")

    # Google Cloud 설정 - 기본값 없음, 필수 설정
    GOOGLE_CLOUD_PROJECT_ID: str = os.getenv("GOOGLE_CLOUD_PROJECT_ID", "") 

    # STT (Speech-to-Text) 설정
    STT_SAMPLE_RATE: int = int(os.getenv("STT_SAMPLE_RATE", "16000")) # 오디오 샘플링 레이트 (Hz)
    STT_LANGUAGE_CODES: List[str] = os.getenv("STT_LANGUAGE_CODES", "en-US,ko-KR").split(",") # 인식할 언어 코드 목록 (BCP-47 형식)
    STT_MODEL: str = os.getenv("STT_MODEL", "telephony") # 사용할 STT 모델

    # --- LLM (Gemini) 관련 설정 ---
    GEMINI_MODEL: str = os.getenv("GEMINI_MODEL", "gemini-1.5-flash-002") # Vertex AI에서 사용 가능한 모델 확인 필요
    USE_VERTEX_AI: bool = os.getenv("USE_VERTEX_AI", "True").lower() == "true" # 기본값은 True로 설정
    VERTEX_AI_LOCATION: str = os.getenv("VERTEX_AI_LOCATION", "asia-northeast3") # Vertex AI 리전 설정

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

# 필수 환경 변수 검증
def validate_required_settings():
    """필수 환경 변수가 설정되었는지 검증하고, 누락된 경우 오류 메시지를 생성합니다."""
    missing_vars = []
    
    # Google Cloud 필수 설정
    if not settings.GOOGLE_CLOUD_PROJECT_ID:
        missing_vars.append("GOOGLE_CLOUD_PROJECT_ID")
    if not settings.VERTEX_AI_LOCATION:
        missing_vars.append("VERTEX_AI_LOCATION")
    
    # TTS 필수 설정
    if not settings.TTS_VOICE_NAME:
        missing_vars.append("TTS_VOICE_NAME")
    if not settings.TTS_LANGUAGE_CODE:
        missing_vars.append("TTS_LANGUAGE_CODE")
    
    # 누락된 환경 변수가 있으면 오류 발생
    if missing_vars:
        raise ValueError(
            f"다음 필수 환경 변수가 설정되지 않았습니다: {', '.join(missing_vars)}.\n"
            "환경 변수나 .env 파일에 이 값들을 설정해주세요.\n"
            "이는 보안을 위해 하드코딩된 기본값을 제거한 결과입니다."
        )
    
    # CORS 설정 검증
    if "*" in settings.ALLOWED_ORIGINS and ENVIRONMENT == "production":
        import warnings
        warnings.warn(
            "보안 경고: 프로덕션 환경에서 모든 오리진(*)을 허용하는 CORS 설정이 감지되었습니다.\n"
            "프로덕션 환경에서는 정확한 도메인 목록을 ALLOWED_ORIGINS 환경 변수에 설정하세요."
        )

# 필수 환경 변수 검증 실행
validate_required_settings() 