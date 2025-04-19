# backend/app/services/tts_service.py
import logging
import asyncio
from google.cloud import texttospeech # 동기 클라이언트 사용
# from google.cloud.texttospeech_v1.types import cloud_tts # 동기 타입 사용 (필요시)
from ..core.config import settings
from typing import AsyncIterator, Iterator, Iterable, List # Iterator, Iterable, List 임포트

# 로거 설정
logger = logging.getLogger(__name__)

# --- 동기 TTS 스트리밍 처리 함수 (별도 스레드에서 실행될 함수) ---
def _blocking_tts_stream(text_chunks: Iterable[str], voice_name: str, language_code: str) -> Iterator[bytes]:
    """
    주어진 텍스트 청크 목록을 받아 동기적으로 TTS 스트리밍을 처리하고 오디오 청크를 반환합니다.
    주의: 이 함수는 동기 함수이며, asyncio 이벤트 루프에서 직접 호출하면 블로킹됩니다.
          asyncio.to_thread를 사용하여 별도 스레드에서 실행해야 합니다.

    Args:
        text_chunks: TTS로 변환할 텍스트 청크의 반복 가능한 객체 (예: 리스트).
        voice_name: 사용할 TTS 음성 이름.
        language_code: 사용할 언어 코드.

    Yields:
        bytes: 생성된 오디오 데이터 청크.
    """
    try:
        client = texttospeech.TextToSpeechClient()
        logger.debug("동기 TTS 클라이언트 생성 완료 (스레드 내).")

        # 스트리밍 설정
        streaming_config = texttospeech.StreamingSynthesizeConfig(
            voice=texttospeech.VoiceSelectionParams(
                name=voice_name,
                language_code=language_code,
            ),
            # audio_config=texttospeech.AudioConfig(audio_encoding=texttospeech.AudioEncoding.LINEAR16)
        )

        # 요청 생성기 (동기)
        def request_generator():
            # 첫 요청: 설정 정보
            yield texttospeech.StreamingSynthesizeRequest(
                streaming_config=streaming_config
            )
            logger.debug("동기 TTS: 초기 설정 요청 생성 (스레드 내).")

            # 두 번째 이후 요청: 텍스트 청크
            count = 0
            for text in text_chunks:
                if text: # 빈 청크는 보내지 않음
                    logger.debug(f"동기 TTS: 텍스트 청크 '{text[:30]}...' 처리 중 (스레드 내).")
                    yield texttospeech.StreamingSynthesizeRequest(
                        input=texttospeech.StreamingSynthesisInput(text=text)
                    )
                    count += 1
            logger.debug(f"동기 TTS: 총 {count}개의 텍스트 청크 요청 생성 완료 (스레드 내).")

        # 동기 스트리밍 API 호출
        logger.info(f"동기 TTS: 스트리밍 합성 시작 (Voice: {voice_name}, Lang: {language_code}) (스레드 내)...")
        responses = client.streaming_synthesize(requests=request_generator())

        # 응답 처리 (오디오 청크 생성)
        for response in responses:
            if response.audio_content:
                logger.debug(f"동기 TTS: 오디오 청크 수신 ({len(response.audio_content)} bytes) (스레드 내).")
                yield response.audio_content
            else:
                logger.debug("동기 TTS: 오디오 콘텐츠 없는 응답 수신 (스레드 내).")

        logger.info("동기 TTS: 스트리밍 합성 처리 완료 (스레드 내).")

    except Exception as e:
        logger.error(f"동기 TTS 스트리밍 중 오류 발생 (스레드 내): {e}", exc_info=True)
        # 오류 발생 시 빈 스트림을 반환하거나 예외를 다시 발생시킬 수 있음
        raise # 호출자(asyncio.to_thread)에게 예외 전파

# --- 비동기 인터페이스 함수 (라우터에서 호출) ---
async def synthesize_speech_stream(text_iterator: AsyncIterator[str]) -> AsyncIterator[bytes]:
    """
    비동기 텍스트 스트림을 받아 동기 TTS 스트리밍을 별도 스레드에서 처리하고,
    결과 오디오 청크 스트림을 비동기적으로 반환합니다.

    Args:
        text_iterator: LLM으로부터 받는 텍스트 청크를 생성하는 비동기 이터레이터.

    Yields:
        bytes: 생성된 오디오 데이터 청크.
    """
    logger.info("TTS 서비스 (동기 모드): 비동기 인터페이스 시작.")
    all_text_chunks: List[str] = []
    try:
        # 경고: LLM 스트림의 모든 텍스트를 먼저 수집합니다.
        # 이는 LLM -> TTS 간 실시간 스트리밍 이점을 감소시킬 수 있습니다.
        logger.warning("TTS 서비스 (동기 모드): LLM 텍스트 스트림을 먼저 모두 수집합니다...")
        async for chunk in text_iterator:
            if chunk:
                all_text_chunks.append(chunk)
        logger.info(f"TTS 서비스 (동기 모드): 총 {len(all_text_chunks)}개의 텍스트 청크 수집 완료.")

        if not all_text_chunks:
            logger.info("TTS 서비스 (동기 모드): 변환할 텍스트가 없어 종료합니다.")
            # 빈 AsyncIterator를 반환하기 위한 처리
            if False: # 이 코드는 실행되지 않지만, async generator를 만들기 위해 필요
                 yield b''
            return # 빈 리스트면 아무것도 yield하지 않고 종료

        # 설정 가져오기
        voice_name = settings.TTS_VOICE_NAME
        language_code = settings.TTS_LANGUAGE_CODE

        # 동기 TTS 함수를 별도 스레드에서 실행
        logger.info("TTS 서비스 (동기 모드): asyncio.to_thread를 사용하여 동기 TTS 작업 시작...")
        sync_audio_iterator: Iterator[bytes] = await asyncio.to_thread(
            _blocking_tts_stream, all_text_chunks, voice_name, language_code
        )
        logger.info("TTS 서비스 (동기 모드): 동기 TTS 작업 완료, 오디오 스트림 처리 시작.")

        # 동기 이터레이터 결과를 비동기적으로 yield
        # 참고: sync_audio_iterator는 이미 완료된 동기 함수의 결과(이터레이터)입니다.
        #       따라서 이 루프 자체는 블로킹되지 않습니다.
        count = 0
        for audio_chunk in sync_audio_iterator:
            yield audio_chunk
            count += 1
            logger.debug(f"TTS 서비스 (동기 모드): 오디오 청크 생성(yield) 완료 ({count}번째).")

        logger.info(f"TTS 서비스 (동기 모드): 총 {count}개의 오디오 청크 생성 완료.")

    except asyncio.CancelledError:
        logger.info("TTS 서비스 (동기 모드): 비동기 인터페이스 작업 취소됨.")
        raise # 취소 예외 전파
    except Exception as e:
        logger.error(f"TTS 서비스 (동기 모드): 비동기 인터페이스 처리 중 오류 발생: {e}", exc_info=True)
        # 오류 발생 시 예외를 다시 발생시켜 호출자(라우터)가 처리하도록 함
        raise
    finally:
        logger.info("TTS 서비스 (동기 모드): 비동기 인터페이스 종료.")

