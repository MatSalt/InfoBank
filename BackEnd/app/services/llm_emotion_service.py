import logging
from google import genai
from google.genai.types import HttpOptions
from ..core.config import settings

logger = logging.getLogger(__name__)

# 감정 분석용 스키마 정의
EMOTION_SCHEMA = {
  "anyOf": [
    {
      "type": "OBJECT",
      "properties": {
        "emotion": {
          "type": "STRING",
          "description": "입력된 글에서 느껴지는 주요 감정. 반드시 제시된 목록 중 하나의 단어여야 합니다.",
          "enum": [
            "기쁨", "화남", "짜증", "속상함", "슬픔", 
            "행복", "놀라움", "부끄러움", "싫증", "귀찮음"
          ]
        }
      },
      "required": ["emotion"]
    }
  ]
}

async def analyze_emotion(text: str, client_info: str = "Unknown") -> dict:
    """
    사용자 텍스트에서 감정을 분석하여 JSON 형태로 반환
    
    Args:
        text: 분석할 텍스트 (사용자 발화)
        client_info: 클라이언트 정보 (로깅용)
        
    Returns:
        dict: {"emotion": "감정"} 형태의 결과
    """
    logger.info(f"[{client_info}] 감정 분석 요청: '{text[:50]}...'")
    
    try:
        # Gemini API 클라이언트 생성
        client = genai.Client(
            vertexai=True,
            project=settings.GOOGLE_CLOUD_PROJECT_ID,
            location=settings.VERTEX_AI_LOCATION,
            http_options=HttpOptions(api_version="v1")
        )
        
        # 감정 분석을 위한 프롬프트 생성
        prompt = f"""
        다음 텍스트에서 느껴지는 감정을 분석해주세요:
        
        "{text}"
        
        감정을 분석하여 제시된 목록의 단어 중 하나로만 응답해주세요.
        """
        
        # Controlled Generation으로 응답 생성
        response = client.models.generate_content(
            model=settings.GEMINI_MODEL,
            contents=prompt,
            config={
                "response_mime_type": "application/json",
                "response_schema": EMOTION_SCHEMA,
            },
        )
        
        # 응답 결과 파싱 (parts 속성 대신 text 속성 사용)
        emotion_data = response.text
        logger.info(f"[{client_info}] 감정 분석 결과: {emotion_data}")
        
        # JSON 문자열을 딕셔너리로 변환 (이미 딕셔너리라면 그대로 반환)
        if isinstance(emotion_data, str):
            import json
            emotion_data = json.loads(emotion_data)
            
        return emotion_data
        
    except Exception as e:
        logger.error(f"[{client_info}] 감정 분석 중 오류: {e}", exc_info=True)
        # 오류 발생 시 기본 감정 반환
        return {"emotion": "중립"}
