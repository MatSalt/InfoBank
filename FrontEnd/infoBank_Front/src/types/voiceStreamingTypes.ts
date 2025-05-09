// WebSocket 서버로부터 받을 것으로 예상되는 데이터 구조 인터페이스
export interface WebSocketResponse {
  transcript?: string;
  is_final?: boolean;
  error?: string;
  control?: string;
  action?: string;
  reason?: string;
  message?: string;
  status?: string;
  type?: string;
  emotion?: string;
}

// 커스텀 훅의 반환 타입 인터페이스
export interface UseVoiceStreamingReturn {
  isRecording: boolean;
  statusMessage: string;
  errorMessage: string;
  isSupported: boolean;
  isConnecting: boolean;
  transcript: string;
  startRecording: () => Promise<void>;
  stopRecording: () => void;
  isResponseProcessing: boolean;
  responseStatusMessage: string;
  processingTime: number | null;
  isPlayingAudio: boolean;
  lastAudioData: Float32Array | null;
  currentEmotion: string;
}

// 전역 Window 인터페이스 확장 정의
export interface CustomWindow extends Window {
  webkitAudioContext?: typeof AudioContext;
} 