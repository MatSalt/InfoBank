/**
 * 환경 변수 설정
 * 
 * Vite에서는 환경 변수에 접근하기 위해 'VITE_' 접두사가 필요합니다.
 * 기본값을 설정하여 환경 변수가 없는 경우에도 작동하도록 합니다.
 */

// 백엔드 URL 기본값
const DEFAULT_BACKEND_URL = 'localhost:8080';

// WebSocket URL
export const WS_URL = import.meta.env.VITE_BACKEND_WS_URL || 
  `ws://${DEFAULT_BACKEND_URL}/ws/audio`;
