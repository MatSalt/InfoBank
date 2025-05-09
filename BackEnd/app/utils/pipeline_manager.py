"""
파이프라인 관리 유틸리티 모듈.

이 모듈은 STT/LLM/TTS 파이프라인 처리를 위한 기능을 제공합니다.
"""
import logging
import asyncio
import time
from typing import AsyncIterator, Dict, Any
from fastapi import WebSocket
from starlette.websockets import WebSocketState

from app.services.llm_service import stream_llm_response
from app.services.tts_service import synthesize_speech_stream
from app.services.llm_emotion_service import analyze_emotion
from app.utils.text_processor import chunk_text_by_punctuation

# 로거 설정
logger = logging.getLogger(__name__)

async def handle_llm_and_tts(transcript: str, ws: WebSocket, client_id: str, user_id: str, is_connected: bool) -> None:
    """
    LLM 응답을 받아 자연스럽게 청킹하고, TTS로 변환하여 WebSocket으로 오디오 청크를 전송합니다.
    
    Args:
        transcript: 사용자 발화 텍스트
        ws: WebSocket 연결 객체
        client_id: 클라이언트 식별자 (로깅용)
        user_id: 사용자 고유 ID
        is_connected: 연결 상태 플래그
        
    Returns:
        None
    """
    logger.info(f"[{client_id}] LLM->청커->TTS 파이프라인 시작: '{transcript[:50]}...'")
    
    try:
        # LLM 호출 직전에 마이크 비활성화 요청 전송
        if is_connected and ws.client_state == WebSocketState.CONNECTED:
            await ws.send_json({
                "control": "response_status",
                "action": "start_processing",
                "reason": "processing",
                "message": "AI가 응답 중입니다..."
            })
            logger.debug(f"[{client_id}] 응답 처리 시간 측정 시작 신호 전송")
        
        # 기존 LLM 및 TTS 스트리밍 로직
        llm_stream = stream_llm_response(transcript, client_id, user_id)
        processed_text_stream = chunk_text_by_punctuation(llm_stream)
        tts_stream = synthesize_speech_stream(processed_text_stream)
        
        # TTS 오디오 전송 시작 시간 기록
        tts_start_time = time.time()
        audio_chunks_sent = 0
        
        # TTS 오디오 청크 전송
        async for audio_chunk in tts_stream:
            if not is_connected:
                break
            
            if ws.client_state == WebSocketState.CONNECTED:
                await ws.send_bytes(audio_chunk)
                audio_chunks_sent += 1
        
        # 오디오 전송 완료 시간 기록
        tts_end_time = time.time()
        tts_duration = tts_end_time - tts_start_time
        logger.info(f"[{client_id}] TTS 오디오 전송 완료: {audio_chunks_sent}개 청크, {tts_duration:.2f}초 소요")
        
        # 마지막 오디오 청크가 클라이언트에서 재생될 시간 고려 (평균 오디오 청크 길이 대략 0.5초로 가정)
        estimated_playback_time = 0.5  # 마지막 청크의 재생 시간 예상치 (초)
        
        # TTS 전송 완료 후 마이크 활성화 요청 전송
        if is_connected and ws.client_state == WebSocketState.CONNECTED:
            await ws.send_json({
                "control": "response_status",
                "action": "end_processing",
                "reason": "processing_complete",
                "message": "AI 응답이 완료되었습니다. 대화를 계속하세요.",
                "audioInfo": {
                    "chunksSent": audio_chunks_sent,
                    "estimatedDuration": tts_duration
                }
            })
            logger.debug(f"[{client_id}] 응답 처리 완료 신호 전송")
    
    except Exception as e:
        logger.error(f"[{client_id}] TTS 스트림 처리 중 오류: {e}", exc_info=True)
        # 오류 발생 시에도 마이크 활성화 요청 전송
        if is_connected and ws.client_state == WebSocketState.CONNECTED:
            try:
                await ws.send_json({
                    "control": "response_status",
                    "action": "end_processing",
                    "reason": "error",
                    "message": "오류가 발생했습니다. 다시 시도해주세요."
                })
            except Exception as send_err:
                logger.error(f"[{client_id}] 오류 후 응답 처리 완료 메시지 전송 중 추가 오류: {send_err}")

async def handle_emotion_analysis(transcript: str, ws: WebSocket, client_id: str) -> None:
    """
    사용자 발화의 감정을 분석하고 결과를 WebSocket으로 전송합니다.
    
    Args:
        transcript: 사용자 발화 텍스트
        ws: WebSocket 연결 객체
        client_id: 클라이언트 식별자 (로깅용)
        
    Returns:
        None
    """
    try:
        # 감정 분석 실행
        emotion_result = await analyze_emotion(transcript, client_id)
        
        if emotion_result and "emotion" in emotion_result:
            logger.info(f"[{client_id}] 감정 분석 결과: {emotion_result['emotion']}")
            
            # 감정 분석 결과를 WebSocket으로 전송
            if ws.client_state == WebSocketState.CONNECTED:
                await ws.send_json({
                    "type": "emotion_result",
                    "emotion": emotion_result["emotion"]
                })
                logger.debug(f"[{client_id}] 감정 분석 결과 전송 완료")
        else:
            logger.warning(f"[{client_id}] 감정 분석 결과가 없거나 형식이 잘못됨: {emotion_result}")
            
    except Exception as e:
        logger.error(f"[{client_id}] 감정 분석 처리 중 오류: {e}", exc_info=True)
        # 오류 시 기본 감정 전송
        if ws.client_state == WebSocketState.CONNECTED:
            try:
                await ws.send_json({
                    "type": "emotion_result",
                    "emotion": "중립",
                    "error": str(e)
                })
            except Exception as send_err:
                logger.error(f"[{client_id}] 감정 오류 메시지 전송 중 추가 오류: {send_err}") 