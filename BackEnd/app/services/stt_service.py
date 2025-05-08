# backend/app/services/stt_service.py
import logging
import asyncio
import time
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

# --- 재연결 설정 ---
MAX_RECONNECT_ATTEMPTS = 5  # 최대 재연결 시도 횟수
BASE_BACKOFF_TIME = 1.0     # 초기 백오프 시간(초)
MAX_BACKOFF_TIME = 10.0     # 최대 백오프 시간(초)

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
    
    Args:
        audio_queue: 오디오 데이터를 포함하는 큐
        result_callback: 결과 처리를 위한 콜백 함수.
                         형식: async def callback(transcript, is_final, speech_event=None)
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

        # 음성 검출을 추적하기 위한 변수
        last_response_time = None
        
        # 응답 처리
        async for response in responses:
            logger.debug(f"STT 서비스: Google로부터 응답 수신: {response}")
            logger.debug(f"STT 서비스: 응답 타입: {type(response)}")
            
            # 모든 response 수신은 인터럽션 신호로 간주할 수 있음
            # response 객체 존재 자체가 음성 입력이 있다는 신호로 간주
            current_time = asyncio.get_event_loop().time()
            
            # 새로운 인터럽션 신호 처리 - 음성 검출을 response 객체로 판단
            # 충분한 시간 간격이 있는 경우에만 인터럽션으로 처리
            # (너무 빈번한 인터럽션 방지)
            if last_response_time is None or (current_time - last_response_time) > 1.0:
                # response 객체 수신 자체를 인터럽션 신호로 간주하여 콜백 호출
                await result_callback(None, False, speech_event={
                    "type": "INTERRUPTION_SIGNAL"
                })
                logger.debug("STT 서비스: 인터럽션 신호 전달 (response 객체 수신)")
            
            last_response_time = current_time
            
            # 기존 결과 처리 코드
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

# --- 자동 재연결을 지원하는 STT 스트리밍 처리 함수 ---
async def start_stt_with_auto_reconnect(audio_queue: asyncio.Queue, result_callback: callable):
    """
    STT 스트리밍을 시작하고 타임아웃 발생 시 자동으로 재연결합니다.
    audio_queue를 유지하면서 연결 상태 변경을 클라이언트에게 알립니다.
    
    Args:
        audio_queue: 오디오 데이터를 포함하는 큐 (재연결 시에도 유지됨)
        result_callback: 결과 처리를 위한 콜백 함수
    """
    reconnect_count = 0
    backoff_time = BASE_BACKOFF_TIME
    
    while True:
        try:
            # STT 스트리밍 시작
            await handle_stt_stream(audio_queue, result_callback)
            
            # 정상 종료된 경우 루프 종료
            logger.info("STT 스트림이 정상적으로 종료되었습니다.")
            break
            
        except STTTimeoutError:
            # 5분 타임아웃 발생 시 재연결 시도
            reconnect_count += 1
            logger.warning(f"STT 타임아웃 감지, 재연결 시도 #{reconnect_count}/{MAX_RECONNECT_ATTEMPTS}")
            
            # 클라이언트에 재연결 상태 알림
            await result_callback(None, False, speech_event={
                "type": "STT_RECONNECTING",
                "attempt": reconnect_count,
                "max_attempts": MAX_RECONNECT_ATTEMPTS
            })
            
            # 재연결 전 잠시 대기 (지수 백오프)
            logger.info(f"재연결 전 {backoff_time:.1f}초 대기...")
            await asyncio.sleep(backoff_time)
            
            # 백오프 시간 증가 (지수적으로)
            backoff_time = min(backoff_time * 1.5, MAX_BACKOFF_TIME)
            
            # 최대 재시도 횟수 확인
            if reconnect_count >= MAX_RECONNECT_ATTEMPTS:
                logger.error(f"STT 재연결 최대 시도 횟수({MAX_RECONNECT_ATTEMPTS})를 초과했습니다.")
                
                # 클라이언트에 재연결 실패 알림
                await result_callback(None, False, speech_event={
                    "type": "STT_RECONNECTION_FAILED",
                    "message": f"STT 서비스 재연결 실패 ({MAX_RECONNECT_ATTEMPTS}회 시도 후)"
                })
                
                # 심각한 오류로 간주하고 예외 발생
                raise RuntimeError(f"STT 서비스 재연결 실패 ({MAX_RECONNECT_ATTEMPTS}회 시도 후)")
            
            # 재연결 성공 시 백오프 시간 초기화
            if reconnect_count > 0 and reconnect_count < MAX_RECONNECT_ATTEMPTS:
                # 클라이언트에 재연결 성공 알림
                await result_callback(None, False, speech_event={
                    "type": "STT_RECONNECTED",
                    "attempt": reconnect_count
                })
                logger.info(f"STT 서비스 재연결 성공 (시도 #{reconnect_count})")
                
        except asyncio.CancelledError:
            # 외부에서 태스크가 취소된 경우
            logger.info("STT 자동 재연결 태스크가 취소되었습니다.")
            raise
            
        except Exception as e:
            # 그 외 예외는 심각한 오류로 간주하고 재시도하지 않음
            logger.error(f"STT 스트리밍 중 복구 불가능한 오류 발생: {e}", exc_info=True)
            
            # 클라이언트에 오류 알림
            await result_callback(None, False, speech_event={
                "type": "STT_ERROR",
                "error": str(e)
            })
            
            # 호출자에게 예외 전파
            raise
