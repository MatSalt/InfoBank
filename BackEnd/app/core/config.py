from pydantic_settings import BaseSettings
from typing import List
import os
from dotenv import load_dotenv

# .env 파일로부터 환경 변수 로드
load_dotenv()

class Settings(BaseSettings):
    # 서버 설정
    SERVER_HOST: str = os.getenv("SERVER_HOST", "0.0.0.0") # 서버 호스트 주소
    SERVER_PORT: int = int(os.getenv("SERVER_PORT", "8000")) # 서버 포트
    
    # 데이터베이스 설정 (필요시 사용)
    # DATABASE_URL: str = os.getenv("DATABASE_URL", "sqlite:///./infobank.db")
    
    # 보안 설정 (필요시 사용)
    # SECRET_KEY: str = os.getenv("SECRET_KEY", "your-secret-key-here") # 비밀 키
    # ALGORITHM: str = os.getenv("ALGORITHM", "HS256") # 토큰 암호화 알고리즘
    # ACCESS_TOKEN_EXPIRE_MINUTES: int = int(os.getenv("ACCESS_TOKEN_EXPIRE_MINUTES", "30")) # 접근 토큰 만료 시간(분)
    
    # CORS 설정
    ALLOWED_ORIGINS: List[str] = os.getenv("ALLOWED_ORIGINS", "http://localhost:5173,http://127.0.0.1:5173").split(",")

    # Google Cloud 설정
    GOOGLE_CLOUD_PROJECT_ID: str = os.getenv("GOOGLE_CLOUD_PROJECT_ID", "your-gcp-project-id") # <- 환경 변수 설정 또는 값 교체 필요

    # STT (Speech-to-Text) 설정
    STT_SAMPLE_RATE: int = int(os.getenv("STT_SAMPLE_RATE", "16000")) # 오디오 샘플링 레이트 (Hz)
    STT_LANGUAGE_CODES: List[str] = os.getenv("STT_LANGUAGE_CODES", "en-US,ko-KR").split(",") # 인식할 언어 코드 목록 (BCP-47 형식)
    STT_MODEL: str = os.getenv("STT_MODEL", "telephony") # 사용할 STT 모델

    # --- LLM (Gemini) 관련 설정 ---
    GEMINI_API_KEY: str = os.getenv("GEMINI_API_KEY", "") # Gemini API 키
    GEMINI_MODEL: str = os.getenv("GEMINI_MODEL", "gemini-2.0-flash-lite-001") # 사용할 Gemini 모델

    class Config:
        # .env 파일이 존재하면 로드
        env_file = ".env"
        env_file_encoding = 'utf-8' # 인코딩 설정
        extra = "allow"  # 추가 필드 허용

# 설정 객체 인스턴스 생성
settings = Settings()

# 필수 환경 변수 확인 (GCP Project ID)
if settings.GOOGLE_CLOUD_PROJECT_ID == "your-gcp-project-id" or not settings.GOOGLE_CLOUD_PROJECT_ID:
    raise ValueError("GOOGLE_CLOUD_PROJECT_ID가 설정되지 않았습니다. 환경 변수나 .env 파일에 설정해주세요.") 