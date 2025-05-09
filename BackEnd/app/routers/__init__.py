from fastapi import APIRouter
from .voice_chat_router import router as voice_router

# 모든 라우터를 하나로 결합
api_router = APIRouter()
api_router.include_router(voice_router) 