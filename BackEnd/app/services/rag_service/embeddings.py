import logging
from google import genai
from google.genai.types import EmbedContentConfig
from typing import List

logger = logging.getLogger(__name__)

class GenAIEmbeddings:
    """Google GenAI 모델을 이용한 임베딩 클래스"""
    
    def __init__(self, client: genai.Client, model_name: str):
        self.client = client
        self.model_name = model_name
        
    def embed_documents(self, texts: List[str]) -> List[List[float]]:
        """문서 리스트에 대한 임베딩 생성"""
        all_embeddings = []
        batch_size = 10
        
        for i in range(0, len(texts), batch_size):
            batch_texts = texts[i:i+batch_size]
            try:
                response = self.client.models.embed_content(
                    model=self.model_name,
                    contents=batch_texts,
                    config=EmbedContentConfig(
                        task_type="RETRIEVAL_DOCUMENT",
                        output_dimensionality=768,
                    )
                )
                
                batch_embeddings = [embedding.values for embedding in response.embeddings]
                all_embeddings.extend(batch_embeddings)
            except Exception as e:
                logger.error(f"배치 {i}에서 임베딩 생성 오류: {e}")
                # 에러 발생 시 오류 처리 로직
                for _ in range(len(batch_texts)):
                    all_embeddings.append([0.0] * 768)
            
        return all_embeddings
    
    def embed_query(self, text: str) -> List[float]:
        """검색 쿼리에 대한 임베딩 생성"""
        try:
            response = self.client.models.embed_content(
                model=self.model_name,
                contents=[text],
                config=EmbedContentConfig(
                    task_type="RETRIEVAL_QUERY",
                    output_dimensionality=768,
                )
            )
            return response.embeddings[0].values
        except Exception as e:
            logger.error(f"쿼리 임베딩 생성 중 오류: {e}")
            # 오류 발생 시 임시 임베딩 생성
            return [0.0] * 768 