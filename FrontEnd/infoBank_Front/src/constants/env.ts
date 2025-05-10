/**
 * 환경 변수 설정
 * 
 * Vite에서는 환경 변수에 접근하기 위해 'VITE_' 접두사가 필요합니다.
 * 기본값을 설정하여 환경 변수가 없는 경우에도 작동하도록 합니다.
 */

// 백엔드 URL 기본값 (Cloud Run에 배포된 URL)
const DEFAULT_BACKEND_URL = import.meta.env.VITE_BACKEND_URL || 'localhost:8000';

// WebSocket URL (Cloud Run은 HTTPS를 사용하므로 WSS 프로토콜을 사용)
export const WS_URL = import.meta.env.VITE_BACKEND_WS_URL || 
  `wss://${DEFAULT_BACKEND_URL}/ws/audio`;

// HTTP API URL (추후 필요 시 사용)
export const API_URL = import.meta.env.VITE_BACKEND_API_URL || 
  `https://${DEFAULT_BACKEND_URL}`;
