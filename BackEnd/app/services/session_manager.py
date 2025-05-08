import logging
from google import genai
from google.genai.types import HttpOptions
from ..core.config import settings
from typing import Dict, Any

logger = logging.getLogger(__name__)

class ChatSessionManager:
    """사용자별 채팅 세션을 관리하는 클래스"""
    def __init__(self):
        """채팅 세션 관리자 초기화"""
        self.sessions: Dict[str, Any] = {}  # {user_id: chat_session}
        self.client = None  # genai.Client 인스턴스
    
    def get_client(self) -> genai.Client:
        """genai.Client 인스턴스를 가져오거나 생성합니다."""
        if self.client is None:
            self.client = genai.Client(
                vertexai=True,
                project=settings.GOOGLE_CLOUD_PROJECT_ID,
                location=settings.VERTEX_AI_LOCATION,
                http_options=HttpOptions(api_version="v1")
            )
            logger.debug(f"genai.Client 생성 완료 (Vertex AI: project={settings.GOOGLE_CLOUD_PROJECT_ID}, location={settings.VERTEX_AI_LOCATION}).")
        return self.client
    
    def get_session(self, user_id: str) -> Any:
        """사용자의 채팅 세션을 가져오거나 생성합니다."""
        if user_id not in self.sessions:
            client = self.get_client()
            model_name = settings.GEMINI_MODEL
            self.sessions[user_id] = client.chats.create(model=model_name)
            logger.debug(f"새 채팅 세션 생성됨 (사용자: {user_id}, 모델: {model_name})")
        
        return self.sessions[user_id]
    
    def clear_session(self, user_id: str) -> None:
        """사용자의 채팅 세션을 초기화합니다."""
        if user_id in self.sessions:
            del self.sessions[user_id]
            logger.debug(f"채팅 세션 초기화됨 (사용자: {user_id})")
    
    def clear_all_sessions(self) -> None:
        """모든 채팅 세션을 초기화합니다."""
        self.sessions.clear()
        logger.debug("모든 채팅 세션 초기화됨")

# 전역 인스턴스
chat_session_manager = ChatSessionManager()
