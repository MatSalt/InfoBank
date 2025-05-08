import re

# 42서울 관련 키워드 목록
SEOUL42_KEYWORDS = ["42", "서울", "과제", "평가", "클러스터", "블랙홀", "이노베이션", 
                    "피씨나", "피신", "동료평가", "트랜센던스"]

# 간단한 인사말/질문 패턴
SIMPLE_PATTERNS = [
    r"^안녕+[!?]*$",
    r"^ㅎㅇ+[!?]*$",
    r"^하이+[!?]*$",
    # 기타 패턴들...
]

def is_simple_question(query: str) -> bool:
    """간단한 질문인지 확인"""
    normalized_query = query.lower().strip()
    
    # 간단한 패턴과 일치하는지 확인
    for pattern in SIMPLE_PATTERNS:
        if re.match(pattern, normalized_query):
            return True
    
    # 매우 짧은 질문(3단어 이하)이고 42서울 관련 키워드가 없으면 간단한 질문으로 간주
    if len(normalized_query.split()) <= 3 and not any(keyword in normalized_query for keyword in SEOUL42_KEYWORDS):
        return True
    
    return False

def contains_seoul42_keywords(query: str) -> bool:
    """42서울 관련 키워드를 포함하는지 확인"""
    normalized_query = query.lower().strip()
    return any(keyword in normalized_query for keyword in SEOUL42_KEYWORDS)
