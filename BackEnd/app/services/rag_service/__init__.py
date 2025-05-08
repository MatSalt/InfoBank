"""
42서울 RAG 서비스 모듈

이 모듈은 42서울 관련 키워드를 포함한 질문에 대해
벡터 데이터베이스를 검색하고 관련 정보를 LLM에 제공하는 RAG 기능을 구현합니다.
"""

import logging
import asyncio
from typing import AsyncIterator, Dict, List, Any, Optional

from google import genai
from ..session_manager import chat_session_manager
from .patterns import is_simple_question, contains_seoul42_keywords
from .embeddings import GenAIEmbeddings  
from .vector_store import VectorStoreManager
from .prompt_builder import create_direct_prompt, create_rag_prompt
from ...core.config import settings

logger = logging.getLogger(__name__)

# 벡터 저장소 경로
VECTOR_DB_PATH = "app/data/vector_db"

# RAG 서비스 클래스
class RAGService:
    def __init__(self):
        self.client = None
        self.embeddings = None
        self.vector_store_manager = None
        self.initialized = False
        
    def initialize(self):
        """RAG 서비스 초기화"""
        if self.initialized:
            return
        
        try:
            # GenAI 클라이언트 가져오기
            self.client = chat_session_manager.get_client()
            
            # 임베딩 객체 생성
            embedding_model = getattr(settings, "EMBEDDING_MODEL", "text-multilingual-embedding-002")
            self.embeddings = GenAIEmbeddings(
                self.client, 
                embedding_model
            )
            
            # 벡터 저장소 관리자 초기화
            self.vector_store_manager = VectorStoreManager(
                self.embeddings,
                VECTOR_DB_PATH
            )
            
            # 벡터 저장소 사전 접근 (로딩 확인)
            _ = self.vector_store_manager.vectorstore
            
            self.initialized = True
            logger.info("RAG 서비스 초기화 완료")
        except Exception as e:
            logger.error(f"RAG 서비스 초기화 오류: {e}", exc_info=True)
            raise
    
    async def process_query(self, query: str, client_id: str = "Unknown") -> AsyncIterator[str]:
        """
        사용자 쿼리 처리: 간단한 질문 여부 확인 → 42서울 키워드 확인 → 벡터 검색 → LLM 생성
        """
        if not self.initialized:
            self.initialize()
        
        logger.info(f"[{client_id}] RAG 쿼리 처리 시작: '{query[:50]}...'")
        
        # 간단한 질문인지 확인
        if is_simple_question(query):
            logger.info(f"[{client_id}] 간단한 질문 감지: 벡터 검색 건너뜀")
            
            # 프롬프트 생성 및 LLM 호출
            prompt = create_direct_prompt(query)
            
            # 일반 chat_session 사용 (RAG 없음)
            chat_session = chat_session_manager.get_session(client_id)
            
            try:
                # 스트리밍 응답 생성
                response_stream = await asyncio.to_thread(
                    chat_session.send_message_stream, 
                    prompt
                )
                
                # 응답 텍스트 반환
                for chunk in response_stream:
                    if hasattr(chunk, 'text') and chunk.text:
                        yield chunk.text
            except Exception as e:
                logger.error(f"[{client_id}] 간단한 질문 처리 중 오류: {e}", exc_info=True)
                raise
            
            return
        
        # 42서울 관련 키워드가 있는지 확인
        if not contains_seoul42_keywords(query):
            logger.info(f"[{client_id}] 42서울 키워드 없음: 벡터 검색 건너뜀")
            
            # 일반 프롬프트로 처리
            prompt = create_direct_prompt(query)
            
            # 일반 chat_session 사용
            chat_session = chat_session_manager.get_session(client_id)
            
            try:
                # 스트리밍 응답 생성
                response_stream = await asyncio.to_thread(
                    chat_session.send_message_stream, 
                    prompt
                )
                
                # 응답 텍스트 반환
                for chunk in response_stream:
                    if hasattr(chunk, 'text') and chunk.text:
                        yield chunk.text
            except Exception as e:
                logger.error(f"[{client_id}] 키워드 없는 질문 처리 중 오류: {e}", exc_info=True)
                raise
            
            return
        
        # 42서울 키워드 발견: RAG 처리
        logger.info(f"[{client_id}] 42서울 키워드 감지: 벡터 검색 수행")
        
        try:
            # 벡터 검색 수행
            search_results = await self.vector_store_manager.search(query, k=1)
            
            # RAG 프롬프트 생성
            prompt = create_rag_prompt(query, search_results)
            
            # 동일한 채팅 세션 사용 (RAG와 일반 채팅 통합)
            chat_session = chat_session_manager.get_session(client_id)
            
            # 스트리밍 응답 생성
            response_stream = await asyncio.to_thread(
                chat_session.send_message_stream, 
                prompt
            )
            
            # 응답 텍스트 반환
            for chunk in response_stream:
                if hasattr(chunk, 'text') and chunk.text:
                    yield chunk.text
                    
        except Exception as e:
            logger.error(f"[{client_id}] RAG 처리 중 오류: {e}", exc_info=True)
            raise
            
# 글로벌 RAG 서비스 인스턴스
rag_service = RAGService() 