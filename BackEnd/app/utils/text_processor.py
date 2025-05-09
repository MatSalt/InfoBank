"""
텍스트 처리 유틸리티 모듈.

이 모듈은 텍스트 청킹과 관련된 기능을 제공합니다.
"""
import logging
import asyncio
from typing import AsyncIterator

# 로거 설정
logger = logging.getLogger(__name__)

async def chunk_text_by_punctuation(
    llm_stream: AsyncIterator[str],
    min_length: int = 10, # 최소 길이를 약간 증가
    punctuation: str = '.?!,' # 구두점으로 분할
) -> AsyncIterator[str]:
    """
    LLM 텍스트 스트림을 비동기적으로 소비하고, 텍스트를 누적하여
    구두점이나 최소 길이로 분할된 청크를 생성하여 더 자연스러운 TTS 입력을 제공합니다.
    상위 오류를 적절히 처리합니다.

    Args:
        llm_stream: LLM에서 텍스트 청크를 생성하는 비동기 이터레이터
        min_length: 구두점이 없을 때 생성하기 전에 누적할 대략적인 최소 길이
        punctuation: 문장을 분할할 구두점 문자들을 포함하는 문자열

    Yields:
        str: TTS에 적합한 처리된 텍스트 청크
    """
    temp_chunk = ""
    logger.debug("텍스트 청커 시작.")
    try:
        async for chunk_text in llm_stream:
            if not chunk_text: continue # LLM의 빈 청크 건너뛰기

            temp_chunk += chunk_text
            # print(f"누적된 텍스트: '{temp_chunk}'") # 디버그 로깅

            # 누적된 청크가 분할할 수 있을 만큼 충분히 긴지 확인
            if len(temp_chunk) >= min_length:
                last_punctuation_pos = -1
                # 마지막 구두점의 위치 찾기
                for i, char in enumerate(reversed(temp_chunk)):
                    if char in punctuation:
                        # 문자열 시작부터의 인덱스 계산
                        last_punctuation_pos = len(temp_chunk) - 1 - i
                        break # 마지막 것을 찾았으므로 중단

                if last_punctuation_pos != -1:
                    # 구두점을 찾았으므로, 그것까지의 부분을 생성
                    text_to_yield = temp_chunk[:last_punctuation_pos + 1].strip()
                    if text_to_yield:
                        logger.debug(f"텍스트 청커 생성 (구두점): '{text_to_yield}'")
                        yield text_to_yield
                    # 나머지는 다음 반복을 위해 보관
                    temp_chunk = temp_chunk[last_punctuation_pos + 1:]
                    # print(f"나머지: '{temp_chunk}'") # 디버그 로깅
                else:
                    # 구두점을 찾지 못했지만 길이는 충분함
                    # 전체 청크를 생성하고 초기화
                    # LLM이 구두점을 사용하지 않는 경우 매우 긴 청크가 되는 것을 방지
                    # 대안: 더 오래 기다릴 수 있지만 지연이 증가할 수 있음
                    text_to_yield = temp_chunk.strip()
                    if text_to_yield:
                        logger.debug(f"텍스트 청커 생성 (길이): '{text_to_yield}'")
                        yield text_to_yield
                    temp_chunk = ""

        # 스트림이 끝난 후 남은 텍스트 생성
        if temp_chunk and temp_chunk.strip():
            logger.debug(f"텍스트 청커 생성 (나머지): '{temp_chunk.strip()}'")
            yield temp_chunk.strip()

        logger.debug("텍스트 청커 종료.")

    except asyncio.CancelledError:
         logger.info("텍스트 청커 태스크 취소됨.")
         raise
    except Exception as e:
         logger.error(f"텍스트 청커 생성기 내부 오류: {e}", exc_info=True)
         raise # 호출자에게 다시 발생시킴 