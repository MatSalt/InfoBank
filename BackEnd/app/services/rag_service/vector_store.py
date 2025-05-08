import os
import logging
from langchain_chroma import Chroma
from .embeddings import GenAIEmbeddings
from typing import List, Tuple, Dict, Any, Optional

logger = logging.getLogger(__name__)

class VectorStoreManager:
    """벡터 저장소 관리 클래스"""
    
    def __init__(self, embeddings: GenAIEmbeddings, persist_directory: str):
        self.embeddings = embeddings
        self.persist_directory = persist_directory
        self._vectorstore = None
        
    @property
    def vectorstore(self) -> Chroma:
        """벡터 저장소 인스턴스 로드 또는 생성"""
        if self._vectorstore is None:
            try:
                self._vectorstore = Chroma(
                    persist_directory=self.persist_directory, 
                    embedding_function=self.embeddings
                )
                collection_size = self._vectorstore._collection.count()
                logger.info(f"벡터 저장소 로드 완료: {collection_size}개 문서")
            except Exception as e:
                logger.error(f"벡터 저장소 로드 중 오류: {e}")
                raise
        
        return self._vectorstore
    
    async def search(self, query: str, k: int = 2) -> List[Dict[str, Any]]:
        """쿼리에 관련된 문서 검색"""
        try:
            results = self.vectorstore.similarity_search(query, k=k)
            return [
                {
                    "page_content": doc.page_content,
                    "metadata": doc.metadata
                }
                for doc in results
            ]
        except Exception as e:
            logger.error(f"벡터 검색 중 오류: {e}")
            return [] 