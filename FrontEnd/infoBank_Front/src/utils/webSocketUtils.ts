import { WebSocketResponse } from '../types/voiceStreamingTypes';

/**
 * WebSocket 메시지 처리 관련 유틸리티 함수 모음
 */

/**
 * 텍스트 메시지를 WebSocketResponse 객체로 파싱
 * @param message 수신된 텍스트 메시지
 * @returns 파싱된 WebSocketResponse 객체 또는 null
 */
export function parseWebSocketMessage(message: string): WebSocketResponse | null {
  try {
    return JSON.parse(message) as WebSocketResponse;
  } catch (error) {
    console.error('WebSocket 메시지 파싱 오류:', error);
    return null;
  }
}

/**
 * 감정 분석 결과를 처리
 * @param data WebSocketResponse 객체
 * @returns 감정 문자열 또는 null
 */
export function processEmotionResult(data: WebSocketResponse): string | null {
  if (data.type === "emotion_result" && data.emotion) {
    console.log(`감정 분석 결과 수신: ${data.emotion}`);
    return data.emotion;
  }
  return null;
}

/**
 * 인터럽션 신호인지 확인
 * @param data WebSocketResponse 객체
 * @returns 인터럽션 신호 여부
 */
export function isInterruptionSignal(data: WebSocketResponse): boolean {
  return data.control === 'interruption';
}

/**
 * 응답 상태 메시지 처리
 * @param data WebSocketResponse 객체
 * @returns 처리된 상태 정보 객체
 */
export function processResponseStatus(data: WebSocketResponse): {
  isStartProcessing: boolean;
  isEndProcessing: boolean;
  message: string;
} {
  const result = {
    isStartProcessing: false,
    isEndProcessing: false,
    message: ''
  };

  if (data.control === 'response_status') {
    if (data.action === 'start_processing') {
      result.isStartProcessing = true;
      result.message = data.message || 'AI가 응답 중입니다...';
    } else if (data.action === 'end_processing') {
      result.isEndProcessing = true;
      result.message = data.message || '말씀하세요...';
    }
  }

  return result;
} 