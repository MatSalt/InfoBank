# backend/app/services/stt_service.py
import logging
import asyncio
from google.cloud import speech_v2 as speech
from google.cloud.speech_v2.types import cloud_speech
from google.api_core import exceptions as google_exceptions
from ..core.config import settings # 설정 가져오기

# 로거 설정
logger = logging.getLogger(__name__)

class STTTimeoutError(Exception):
    """Google Cloud STT 스트리밍 타임아웃 시 발생하는 사용자 정의 예외"""
    pass

# --- STT 설정 ---
PROJECT_ID = settings.GOOGLE_CLOUD_PROJECT_ID
RATE = settings.STT_SAMPLE_RATE
LANGUAGE_CODES = settings.STT_LANGUAGE_CODES
MODEL = settings.STT_MODEL
RECOGNIZER_PATH = f"projects/{PROJECT_ID}/locations/global/recognizers/_"

# --- 비동기 STT 요청 생성기 ---
async def request_generator(audio_queue: asyncio.Queue, recognizer: str, config: cloud_speech.StreamingRecognitionConfig):
    """
    STT 요청을 생성하는 비동기 제너레이터: 첫 요청은 설정 정보, 이후는 오디오 청크.

    Args:
        audio_queue: 오디오 청크(bytes) 또는 종료 신호(None)를 포함하는 asyncio.Queue.
        recognizer: Recognizer 리소스 경로.
        config: StreamingRecognitionConfig 객체.
    """
    try:
        # 초기 설정 정보 요청 전송
        yield cloud_speech.StreamingRecognizeRequest(
            recognizer=recognizer,
            streaming_config=config,
        )
        logger.debug("STT 서비스: 초기 설정 요청 전송 완료.")

        # 큐로부터 오디오 청크 스트리밍
        while True:
            chunk = await audio_queue.get()
            if chunk is None:
                logger.debug("STT 서비스: None 청크 수신, 오디오 스트림 중단.")
                break
            logger.debug(f"STT 서비스: 큐에서 {len(chunk)} 바이트 오디오 청크 가져옴.")
            yield cloud_speech.StreamingRecognizeRequest(audio=chunk)
            logger.debug("STT 서비스: 오디오 청크 요청 전송 완료.")
            audio_queue.task_done()

    except asyncio.CancelledError:
        logger.info("STT 서비스: 요청 제너레이터 취소됨.")
    except Exception as e:
        logger.error(f"STT 서비스: 요청 제너레이터 오류 발생: {e}", exc_info=True)
        raise
    finally:
        logger.debug("STT 서비스: 요청 제너레이터 완료.")

# --- STT 스트리밍 처리 함수 ---
async def handle_stt_stream(audio_queue: asyncio.Queue, result_callback: callable):
    """
    오디오 큐로부터 오디오를 받아 STT 스트리밍을 처리하고, 결과를 콜백으로 전달합니다.
    409 타임아웃 발생 시 STTTimeoutError를 발생시킵니다.
    """
    speech_client = None
    responses = None
    try:
        # 비동기 클라이언트 생성
        speech_client = speech.SpeechAsyncClient()

        # STT 설정 정의
        explicit_config = cloud_speech.ExplicitDecodingConfig(
            encoding=cloud_speech.ExplicitDecodingConfig.AudioEncoding.LINEAR16,
            sample_rate_hertz=RATE,
            audio_channel_count=1,
        )
        recognition_config = cloud_speech.RecognitionConfig(
            explicit_decoding_config=explicit_config,
            language_codes=LANGUAGE_CODES,
            model=MODEL,
            features=cloud_speech.RecognitionFeatures(
                # enable_automatic_punctuation=True, # 필요시 활성화
            ),
        )
        streaming_config = cloud_speech.StreamingRecognitionConfig(
            config=recognition_config,
            streaming_features=cloud_speech.StreamingRecognitionFeatures(
                interim_results=True
            )
        )

        # 요청 제너레이터 생성
        requests = request_generator(audio_queue, RECOGNIZER_PATH, streaming_config)

        # STT 스트리밍 API 호출
        logger.info("STT 서비스: 스트리밍 인식 시작...")
        responses = await speech_client.streaming_recognize(requests=requests)

        # 응답 처리
        async for response in responses:
            logger.debug(f"STT 서비스: Google로부터 응답 수신: {response}")
            if not response.results:
                logger.debug("STT 서비스: 결과 없는 응답 수신.")
                continue
            result = response.results[0]
            if not result.alternatives:
                continue

            alternative = result.alternatives[0]
            transcript = alternative.transcript
            is_final = result.is_final

            # 결과를 콜백 함수로 전달
            logger.debug(f"STT 응답 수신: is_final={result.is_final}, transcript={transcript[:50]}...")
            await result_callback(transcript, is_final)
            logger.debug(f"STT 결과 콜백 호출 완료: is_final={result.is_final}")

    except google_exceptions.Aborted as e:
        # 오류 메시지 내용을 확인하여 타임아웃인지 판단
        error_str = str(e).lower()
        if "stream timed out" in error_str or "max duration" in error_str or "409" in error_str:
            logger.warning(f"STT 서비스: 스트리밍 타임아웃(409) 발생: {e}. 재연결 필요 신호 발생.")
            raise STTTimeoutError("STT stream timed out or reached max duration") from e
        else:
            # 타임아웃이 아닌 다른 Aborted 오류 처리
            logger.error(f"STT 서비스: 처리 중 Aborted 오류 발생 (타임아웃 아님): {e}", exc_info=True)
            raise
    except asyncio.CancelledError:
        logger.info("STT 서비스: 스트리밍 처리 취소됨.")
        raise
    except Exception as e:
        logger.error(f"STT 서비스: 스트리밍 처리 중 예상치 못한 오류 발생: {e}", exc_info=True)
        raise
    finally:
        logger.info("STT 서비스: 스트리밍 처리 (한 세션) 완료.")
