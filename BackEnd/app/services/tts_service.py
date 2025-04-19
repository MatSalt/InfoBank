# backend/app/services/tts_service.py
import logging
import asyncio
import concurrent.futures
from google.cloud import texttospeech # 동기 클라이언트 사용
# from google.cloud.texttospeech_v1.types import cloud_tts # 동기 타입 사용 (필요시)
from ..core.config import settings
from typing import AsyncIterator, Iterator, Iterable, List, Tuple, Dict, Optional # Iterator, Iterable, List 임포트

# 로거 설정
logger = logging.getLogger(__name__)

def _process_single_tts_chunk(
    text_chunk: str,
    sequence_number: int,
    client: texttospeech.TextToSpeechClient,
    voice_name: str,
    language_code: str
) -> Tuple[int, Optional[bytes]]:
    """
    단일 텍스트 청크를 동기 TTS 스트리밍 API를 사용하여 처리합니다.
    이 함수는 블로킹이며 스레드 풀 실행기에서 실행되도록 설계되었습니다.

    Args:
        text_chunk: 합성할 단일 텍스트 청크
        sequence_number: 이 청크의 시퀀스 번호
        client: 동기 TextToSpeechClient 인스턴스
        voice_name: 사용할 TTS 음성 이름
        language_code: TTS 언어 코드

    Returns:
        시퀀스 번호와 결과 오디오 바이트(또는 오류 시 None)를 포함하는 튜플
    """
    if not text_chunk or not text_chunk.strip():
        logger.debug(f"스레드 TTS (시퀀스 {sequence_number}): 빈 청크 무시.")
        return sequence_number, None

    logger.debug(f"스레드 TTS (시퀀스 {sequence_number}): 청크 처리 중: '{text_chunk[:30]}...'")
    audio_chunks = []
    try:
        # --- 단일 청크에 대한 동기 요청 생성기 ---
        def request_generator():
            # 1. 설정 요청
            streaming_config = texttospeech.StreamingSynthesizeConfig(
                voice=texttospeech.VoiceSelectionParams(
                    name=voice_name,
                    language_code=language_code,
                ),
                # audio_config=texttospeech.AudioConfig(
                #     audio_encoding=texttospeech.AudioEncoding.LINEAR16,
                #     sample_rate_hertz=24000  # 명시적으로 샘플레이트 설정
                # )
            )
            yield texttospeech.StreamingSynthesizeRequest(streaming_config=streaming_config)
            logger.debug(f"스레드 TTS (시퀀스 {sequence_number}): 설정 요청 전송됨.")

            # 2. 단일 텍스트 청크 요청
            yield texttospeech.StreamingSynthesizeRequest(
                input=texttospeech.StreamingSynthesisInput(text=text_chunk)
            )
            logger.debug(f"스레드 TTS (시퀀스 {sequence_number}): 텍스트 요청 전송됨.")

        # 스트리밍 합성 API 호출
        responses = client.streaming_synthesize(requests=request_generator())

        # 오디오 콘텐츠 수집 (일반적으로 작은 청크의 경우 하나의 응답)
        for response in responses:
            if response.audio_content:
                audio_chunks.append(response.audio_content)

        if audio_chunks:
            full_audio = b"".join(audio_chunks)
            logger.debug(f"스레드 TTS (시퀀스 {sequence_number}): 오디오 생성됨 ({len(full_audio)} bytes).")
            return sequence_number, full_audio
        else:
            logger.warning(f"스레드 TTS (시퀀스 {sequence_number}): 청크에 대한 오디오 콘텐츠가 수신되지 않음.")
            return sequence_number, None

    except Exception as e:
        logger.error(f"스레드 TTS (시퀀스 {sequence_number}): 청크 '{text_chunk[:30]}...' 합성 중 오류 발생: {e}", exc_info=True)
        return sequence_number, None  # 오류 시 None 반환

async def synthesize_speech_stream(text_iterator: AsyncIterator[str]) -> AsyncIterator[bytes]:
    """
    텍스트 청크의 비동기 이터레이터를 받아, 스레드 풀과 동기 Google TTS 클라이언트를 사용하여
    각 청크를 병렬로 처리하고, 결과를 올바른 순서로 비동기적으로 반환합니다.

    Args:
        text_iterator: LLM에서 생성된 텍스트 청크를 제공하는 비동기 이터레이터

    Yields:
        bytes: 올바른 순서로 합성된 오디오 데이터 청크
    """
    logger.info("TTS 서비스 (스레드 동기): 음성 합성 스트림 시작.")
    loop = asyncio.get_running_loop()
    # 루프에서 관리하는 기본 ThreadPoolExecutor 사용
    # max_workers를 조정할 수 있지만 기본값이 대체로 적절함 (CPU 수에 따라 다름)
    # executor = concurrent.futures.ThreadPoolExecutor(max_workers=...)

    # 스레드 간에 공유할 단일 클라이언트 인스턴스 생성
    try:
        tts_client = texttospeech.TextToSpeechClient()
        logger.info("TTS 서비스 (스레드 동기): 공유 TextToSpeechClient 생성됨.")
    except Exception as e:
        logger.error(f"TTS 서비스 (스레드 동기): TextToSpeechClient 생성 실패: {e}", exc_info=True)
        # 클라이언트 생성 실패 시 아무것도 yield하지 않음
        if False: yield b''  # async generator로 만들기 위해 필요
        return

    # 설정 가져오기
    voice_name = settings.TTS_VOICE_NAME
    language_code = settings.TTS_LANGUAGE_CODE

    futures = []
    sequence_counter = 0
    llm_stream_finished = False
    pending_results: Dict[int, Optional[bytes]] = {}  # 순서를 기다리는 결과 저장
    next_expected_sequence = 0
    active_tasks = 0  # 제출된 태스크 추적

    try:
        # 초기 청크에 대한 태스크 제출
        async for text_chunk in text_iterator:
            if text_chunk and text_chunk.strip():
                logger.debug(f"TTS 서비스: 청크 {sequence_counter}를 스레드 풀에 제출.")
                # 블로킹 함수를 스레드 풀 실행기에 제출
                future = loop.run_in_executor(
                    None,  # 기본 실행기 사용
                    _process_single_tts_chunk,
                    text_chunk,
                    sequence_counter,
                    tts_client,  # 공유 클라이언트 인스턴스 전달
                    voice_name,
                    language_code
                )
                futures.append(future)
                sequence_counter += 1
                active_tasks += 1

            # 새 청크를 받는 동시에 완료된 future 처리
            # 무한정 블로킹을 피하기 위해 짧은 타임아웃 사용
            done, pending = await asyncio.wait(futures, return_when=asyncio.FIRST_COMPLETED, timeout=0.01)

            for future in done:
                try:
                    seq, audio_data = future.result()
                    logger.debug(f"TTS 서비스: 시퀀스 {seq}에 대한 스레드 풀 태스크 완료.")
                    pending_results[seq] = audio_data
                    futures.remove(future)  # 완료된 future 제거
                    active_tasks -= 1

                    # 완료된 청크를 순서대로 yield
                    while next_expected_sequence in pending_results:
                        ordered_audio = pending_results.pop(next_expected_sequence)
                        if ordered_audio:
                            logger.debug(f"TTS 서비스: 순서대로 오디오 청크 {next_expected_sequence} yield ({len(ordered_audio)} bytes).")
                            yield ordered_audio
                        else:
                            logger.warning(f"TTS 서비스: 이전 오류 또는 오디오 없음으로 인해 청크 {next_expected_sequence} 건너뜀.")
                        next_expected_sequence += 1

                except Exception as e:
                    # future.result()의 오류를 로깅하지만 계속 진행
                    logger.error(f"TTS 서비스: 스레드 풀 future에서 결과 검색 중 오류: {e}", exc_info=True)
                    futures.remove(future)  # 문제가 있는 future 제거
                    active_tasks -= 1
                    # future 오류 시 시퀀스를 어떻게 처리할까? None으로 표시?
                    # 작업자 함수가 오류 시 (seq, None)을 반환한다고 가정.

        llm_stream_finished = True
        logger.info("TTS 서비스: LLM 텍스트 스트림 종료. 남은 TTS 태스크 대기 중.")

        # 제출된 모든 남은 태스크가 완료될 때까지 대기
        if futures:
            done, pending = await asyncio.wait(futures, return_when=asyncio.ALL_COMPLETED)
            for future in done:
                try:
                    seq, audio_data = future.result()
                    logger.debug(f"TTS 서비스: 남은 스레드 풀 태스크 완료 (시퀀스 {seq}).")
                    pending_results[seq] = audio_data
                    active_tasks -= 1
                except Exception as e:
                    logger.error(f"TTS 서비스: 남은 future에서 결과 검색 중 오류: {e}", exc_info=True)
                    active_tasks -= 1
            # 여기서는 pending future가 없어야 하지만, 있다면 로깅
            if pending:
                logger.error(f"TTS 서비스: ALL_COMPLETED 대기 후에도 {len(pending)}개의 future가 완료되지 않음!")

        # 남은 순서대로 청크 yield
        logger.debug("TTS 서비스: 최종 대기 중인 결과 처리.")
        while next_expected_sequence in pending_results:
            ordered_audio = pending_results.pop(next_expected_sequence)
            if ordered_audio:
                logger.debug(f"TTS 서비스: 최종 순서대로 오디오 청크 {next_expected_sequence} yield ({len(ordered_audio)} bytes).")
                yield ordered_audio
            else:
                logger.warning(f"TTS 서비스: 이전 오류 또는 오디오 없음으로 인해 최종 청크 {next_expected_sequence} 건너뜀.")
            next_expected_sequence += 1

        # 정상성 검사: 모든 제출된 태스크를 처리했는지 확인
        if active_tasks != 0:
            logger.error(f"TTS 서비스: 종료 시 활성 태스크 수 불일치: {active_tasks}")
        if pending_results:
            logger.error(f"TTS 서비스: 모든 결과가 yield되지 않음? 남은 시퀀스: {list(pending_results.keys())}")

    except asyncio.CancelledError:
        logger.info("TTS 서비스 (스레드 동기): 태스크 취소됨.")
        # 미완료된 future 취소
        for future in futures:
            if not future.done():
                future.cancel()
        # 취소가 잠재적으로 등록될 수 있도록 잠시 대기
        await asyncio.sleep(0.1)
        raise  # 취소 전파
    except Exception as e:
        logger.error(f"TTS 서비스 (스레드 동기): 스트림 처리 중 오류 발생: {e}", exc_info=True)
        raise  # 라우터가 처리할 수 있도록 예외를 다시 발생시킴
    finally:
        logger.info("TTS 서비스 (스레드 동기): 음성 합성 스트림 종료.")
        # None과 함께 loop.run_in_executor를 사용할 때는 명시적인 실행기 종료가 필요하지 않음

