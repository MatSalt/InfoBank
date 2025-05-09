# backend/app/main.py
import logging
import uvicorn
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from .routers import api_router
from .core.config import settings
import os
# 라우터 임포트 (voice 라우터)
from app.routers import voice_chat_router as voice
# RAG 서비스 임포트
from app.services.rag_service import rag_service

# 로깅 설정
logging.basicConfig(
    level=logging.INFO, 		# DEBUG, INFO, WARNING, ERROR, CRITICAL
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    datefmt='%Y-%m-%d %H:%M:%S'
)
logger = logging.getLogger(__name__)

# 현재 환경 확인
ENVIRONMENT = os.getenv("ENVIRONMENT", "development").lower()

# FastAPI 애플리케이션 인스턴스 생성
app = FastAPI(
    title="InfoBank API",
    description="InfoBank 백엔드 API 서버",
    version="1.0.0"
)

# CORS 설정
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.ALLOWED_ORIGINS,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# 서버 시작 이벤트 핸들러
@app.on_event("startup")
async def startup_event():
    """서버 시작 시 초기화 작업 수행"""
    # 환경 변수 설정 상태 로깅
    logger.info(f"서버 시작: 환경 변수 설정 확인 (환경: {ENVIRONMENT})")
    logger.info(f"서버 설정: 호스트={settings.SERVER_HOST}, 포트={settings.SERVER_PORT}")
    
    # CORS 설정 로깅
    if "*" in settings.ALLOWED_ORIGINS:
        if ENVIRONMENT == "production":
            logger.warning("보안 경고: 프로덕션 환경에서 모든 오리진(*)을 허용하는 CORS 설정이 감지되었습니다.")
            logger.warning("프로덕션 환경에서는 ALLOWED_ORIGINS 환경 변수에 특정 도메인만 허용하도록 설정하세요.")
            logger.warning("예시: ALLOWED_ORIGINS=https://yourdomain.com,https://admin.yourdomain.com")
        else:
            logger.info("CORS 설정: 모든 오리진 허용 (* 설정 감지됨, 개발 환경에서만 사용하세요)")
    else:
        logger.info(f"CORS 허용 출처: {', '.join(settings.ALLOWED_ORIGINS)}")
    
    logger.info(f"Google Cloud 프로젝트: {settings.GOOGLE_CLOUD_PROJECT_ID}")
    
    # 벡터 저장소 로드
    logger.info("서버 시작 시 벡터 저장소 로드 중...")
    try:
        rag_service.initialize()
        logger.info("벡터 저장소 로드 완료 (2500개 문서)")
    except Exception as e:
        logger.error(f"벡터 저장소 초기 로드 중 오류 발생: {e}", exc_info=True)

# 루트 경로 핸들러 (선택 사항)
@app.get("/")
async def root():
    return {"message": "Welcome to InfoBank API"}

# Voice 라우터 포함
# voice.router에 정의된 모든 경로는 /ws 접두사를 가지게 됨
app.include_router(voice.router)

# 라우터 등록
app.include_router(api_router)

# 서버 실행을 위한 코드 (개발 환경)
if __name__ == "__main__":
    logger.info("Starting Uvicorn server in development mode...")
    uvicorn.run("app.main:app", host=settings.SERVER_HOST, port=settings.SERVER_PORT)

