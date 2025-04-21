# backend/app/main.py
import logging
import uvicorn
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from .routers import api_router
from .core.config import settings
import os
# 라우터 임포트 (voice 라우터)
from app.routers import voice

# 로깅 설정
logging.basicConfig(
    level=logging.INFO, 		# DEBUG, INFO, WARNING, ERROR, CRITICAL
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    datefmt='%Y-%m-%d %H:%M:%S'
)
logger = logging.getLogger(__name__)

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

