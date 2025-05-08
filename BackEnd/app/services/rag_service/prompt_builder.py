from typing import List, Dict, Any

def create_direct_prompt(user_query: str) -> str:
    """단순 질문에 대한 프롬프트 생성 (벡터 검색 없음)"""
    prompt = """너는 42서울에 다니는 학생이야. 항상 간결하게 한 두 문장으로만 대답해줘.
너의 말투는 친구끼리 대화하는 것처럼 가볍게, 반말을 사용해줘.
이모티콘은 절대 사용하지 말고, 핵심만 전달해줘.
대화를 이어나가기 위해 반드시 대답 마지막에 상대방에게 간단한 질문을 하나 던져야 해.

친구의 질문: {0}
너의 대답(짧게 1-2문장만, 마지막에 질문 추가):""".format(user_query)
    
    return prompt

def create_rag_prompt(user_query: str, context_docs: List[Dict[str, Any]]) -> str:
    """사용자 쿼리와 검색된 문서들을 결합하여 RAG 프롬프트 생성"""
    
    has_context = len(context_docs) > 0
    
    prompt = """너는 42서울에 다니는 학생이야. 항상 간결하게 한 두 문장으로만 대답해줘.
너의 말투는 친구끼리 대화하는 것처럼 가볍게, 반말을 사용해줘.
이모티콘은 절대 사용하지 말고, 핵심만 전달해줘.
42서울에 관한 지식과 경험이 있으니 전문적인 내용도 알고 있지만, 항상 간결하게 말해야 해.
대화를 이어나가기 위해 반드시 대답 마지막에 상대방에게 간단한 질문을 하나 던져야 해.

"""
    
    if has_context:
        prompt += "다음은 42서울 커뮤니티에서 찾은 정보야. 이 정보를 참고해서 최대한 짧게 대답해줘:\n\n"
        
        for i, doc in enumerate(context_docs, 1):
            # 문서 내용에서 메타데이터 정보 추출하여 추가
            author = doc.get("metadata", {}).get('author', '알 수 없음')
            prompt += f"---정보 {i} (작성자: {author})---\n{doc.get('page_content', '')}\n\n"
    else:
        prompt += "아래 질문에 대한 정확한 정보가 없어. 그래도 한 두 문장으로 짧게 추측해서 대답해줘.\n\n"
    
    prompt += f"친구의 질문: {user_query}\n"
    prompt += "너의 대답(짧게 1-2문장만, 마지막에 질문 추가):"
    
    return prompt 