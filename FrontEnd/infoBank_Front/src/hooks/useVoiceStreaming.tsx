import { useState, useEffect, useRef, useCallback } from 'react';

// WebSocket 연결 주소 (환경 변수 등으로 관리하는 것이 더 좋습니다)
const WEBSOCKET_URL = 'ws://localhost:8000/ws/audio'; // 예시: 로컬 FastAPI 백엔드

// WebSocket 서버로부터 받을 것으로 예상되는 데이터 구조 인터페이스
interface WebSocketResponse {
  transcript?: string;
  is_final?: boolean;
  error?: string; // 백엔드 에러 메시지 필드 (선택 사항)
}

// 커스텀 훅의 반환 타입 인터페이스
interface UseVoiceStreamingReturn {
  isRecording: boolean;
  statusMessage: string;
  errorMessage: string;
  isSupported: boolean;
  isConnecting: boolean;
  transcript: string;
  startRecording: () => Promise<void>;
  stopRecording: () => void;
}

/**
 * AI 음성 대화 스트리밍을 위한 커스텀 훅 (TypeScript)
 * @returns {UseVoiceStreamingReturn} 음성 스트리밍 관련 상태 및 제어 함수
 */
export function useVoiceStreaming(): UseVoiceStreamingReturn {
  // 상태 변수들 (타입 명시)
  const [isRecording, setIsRecording] = useState<boolean>(false);
  const [statusMessage, setStatusMessage] = useState<string>('버튼을 누르고 말씀하세요.');
  const [errorMessage, setErrorMessage] = useState<string>('');
  const [isSupported, setIsSupported] = useState<boolean>(false);
  const [isConnecting, setIsConnecting] = useState<boolean>(false);
  const [transcript, setTranscript] = useState<string>('');

  // useRef (타입 명시, 초기값 null)
  const mediaRecorderRef = useRef<MediaRecorder | null>(null);
  const webSocketRef = useRef<WebSocket | null>(null);
  const audioStreamRef = useRef<MediaStream | null>(null);

  // 브라우저 지원 여부 확인
  useEffect(() => {
    setIsSupported(!!(navigator.mediaDevices && typeof navigator.mediaDevices.getUserMedia === 'function' && window.WebSocket));
  }, []);

  // 오디오 스트림 중지 함수
  const stopAudioStream = useCallback((): void => {
    if (audioStreamRef.current) {
      audioStreamRef.current.getTracks().forEach(track => track.stop());
      console.log("마이크 스트림 중지됨");
      audioStreamRef.current = null;
    }
  }, []);

  // 녹음 중지 함수 - 먼저 정의
  const stopRecording = useCallback((): void => {
    console.log("녹음 중지 요청됨.");
    // null 체크 추가
    if (mediaRecorderRef.current?.state === 'recording') {
      mediaRecorderRef.current.stop();
    }

    if (webSocketRef.current?.readyState === WebSocket.OPEN) {
      webSocketRef.current.close(1000, "Client stopped recording");
      console.log("WebSocket 연결 종료 요청됨.");
    } else {
      // WebSocket이 없거나 이미 닫혔으면 스트림만 정리
      stopAudioStream();
    }

    // 상태 업데이트는 onclose 핸들러 또는 여기서 직접 수행
    setIsRecording(false);
    setStatusMessage('버튼을 누르고 말씀하세요.');
    mediaRecorderRef.current = null;
    // webSocketRef, audioStreamRef는 onclose 또는 stopAudioStream에서 정리됨
  }, [stopAudioStream]);

  // WebSocket 연결 설정 함수
  const setupWebSocket = useCallback((): Promise<WebSocket> => {
    return new Promise((resolve, reject) => {
      if (webSocketRef.current && webSocketRef.current.readyState !== WebSocket.CLOSED) {
        webSocketRef.current.close();
        console.log("Previous WebSocket connection closed.");
      }

      const ws = new WebSocket(WEBSOCKET_URL);
      ws.binaryType = 'blob'; // 바이너리 타입 설정

      ws.onopen = () => {
        console.log('WebSocket 연결 성공');
        setStatusMessage('연결됨. 녹음 중...');
        setIsConnecting(false);
        webSocketRef.current = ws;
        resolve(ws);
      };

      // 메시지 수신 처리 (타입 명시: MessageEvent)
      ws.onmessage = (event: MessageEvent) => {
         // 서버에서 텍스트(JSON) 또는 Blob을 보낼 수 있으므로 타입 확인
        if (typeof event.data === 'string') {
            console.log('WebSocket 텍스트 메시지 수신:', event.data);
             try {
                const data = JSON.parse(event.data) as WebSocketResponse; // 타입 단언 사용
                if (data.transcript) {
                    setTranscript(prev => prev + data.transcript);
                    setStatusMessage('텍스트 수신 중...');
                }
                 if (data.is_final) {
                    setStatusMessage('최종 결과 수신.');
                    // 최종 결과 처리 로직 (예: 특정 상태 업데이트)
                }
                 if (data.error) {
                    console.error("WebSocket message error:", data.error);
                    setErrorMessage(`서버 오류: ${data.error}`);
                    // 서버 오류 시 녹음 중지 등 추가 처리 가능
                    stopRecording();
                 }
             } catch {
                console.warn("Received non-JSON string message:", event.data);
                // 단순 텍스트 응답 처리 (필요한 경우)
                setTranscript(prev => prev + event.data);
             }
        } else if (event.data instanceof Blob) {
             console.log('WebSocket Blob 메시지 수신:', event.data);
             // 서버에서 오디오 Blob 등을 보낸 경우의 처리 (예: TTS 결과 재생)
        } else {
            console.warn("Received unknown message type:", event.data);
        }
      };

      // 오류 처리 (타입 명시: Event)
      ws.onerror = (event: Event) => {
        console.error('WebSocket 오류:', event);
        setErrorMessage('WebSocket 연결 오류 발생');
        setIsConnecting(false);
        setIsRecording(false);
        setStatusMessage('연결 오류. 다시 시도하세요.');
        reject(new Error('WebSocket error occurred')); // Error 객체로 reject
      };

      // 연결 종료 처리 (타입 명시: CloseEvent)
      ws.onclose = (event: CloseEvent) => {
        console.log('WebSocket 연결 종료:', event.code, event.reason);
        // isRecording 상태는 여기서 직접 참조하기보다 useEffect 등에서 관리하는 것이 더 안전할 수 있음
        // 또는 stopRecording 호출 시 isRecording을 false로 설정하는 것으로 충분
        if (!event.wasClean) { // 비정상 종료 시
          setErrorMessage('WebSocket 연결이 예기치 않게 종료되었습니다.');
          setStatusMessage('연결 끊김. 다시 시도하세요.');
        }
        setIsRecording(false); // 연결 종료 시 녹음 상태 확실히 해제
        setIsConnecting(false);
        webSocketRef.current = null;
        stopAudioStream(); // WebSocket 종료 시 스트림도 확실히 정리
      };
    });
  }, [stopAudioStream]); // isRecording 의존성 제거 (onclose에서 직접 상태 참조 지양)

  // MediaRecorder 설정 및 스트리밍 시작 함수
  const setupAndStartStreaming = useCallback(async (): Promise<boolean> => {
    if (!isSupported) {
      setErrorMessage('마이크 녹음 또는 WebSocket을 지원하지 않는 브라우저입니다.');
      return false;
    }

    try {
      const stream: MediaStream = await navigator.mediaDevices.getUserMedia({ audio: true });
      audioStreamRef.current = stream;

      const options = { mimeType: 'audio/webm;codecs=opus', audioBitsPerSecond: 16000 };
      let recorder: MediaRecorder;
      try {
        recorder = new MediaRecorder(stream, options);
      } catch {
        console.warn("WebM Opus not supported, trying default");
        try {
          recorder = new MediaRecorder(stream);
        } catch (err2) {
          console.error("MediaRecorder not supported with any mimeType:", err2);
          setErrorMessage('오디오 녹음 형식이 지원되지 않습니다.');
          stopAudioStream();
          return false;
        }
      }
      console.log("Using mimeType:", recorder.mimeType);
      mediaRecorderRef.current = recorder;

      const timeSliceMs = 500;

      // 데이터 수신 처리 (타입 명시: BlobEvent)
      recorder.ondataavailable = (event: BlobEvent) => {
        // webSocketRef.current가 null이 아닐 때만 send 호출 (타입 가드)
        if (event.data.size > 0 && webSocketRef.current?.readyState === WebSocket.OPEN) {
          webSocketRef.current.send(event.data);
        } else if (webSocketRef.current && webSocketRef.current.readyState !== WebSocket.OPEN) {
          console.warn("WebSocket is not open. Cannot send audio data.");
        }
      };

      recorder.onstop = () => {
        console.log("MediaRecorder 중지됨.");
      };

      // 오류 처리 (타입 명시: Event - MediaRecorderErrorEvent는 표준이 아님)
      recorder.onerror = (event: Event) => {
        console.error("MediaRecorder 오류:", event);
        // event.error를 직접 사용하기 어려울 수 있음, name으로 구분 시도
        const errorEvent = event as { error?: { name?: string } };
        setErrorMessage(`녹음 중 오류 발생: ${errorEvent.error?.name || 'Unknown error'}`);
        stopRecording(); // 오류 시 녹음 중지 로직 실행
      };

      setIsConnecting(true);
      setStatusMessage('WebSocket 연결 중...');
      await setupWebSocket();

      if (webSocketRef.current?.readyState === WebSocket.OPEN) {
        recorder.start(timeSliceMs);
        console.log(`녹음 및 스트리밍 시작 (timeslice: ${timeSliceMs}ms)`);
        return true;
      } else {
        console.error("WebSocket 연결 실패하여 녹음을 시작할 수 없습니다.");
        // setupWebSocket 내부에서 errorMessage 설정됨
        stopAudioStream();
        return false;
      }

    } catch (err) {
      console.error('마이크 접근 또는 MediaRecorder 설정 오류:', err);
      if (err instanceof Error) { // Error 타입인지 확인
          if (err.name === 'NotAllowedError' || err.name === 'PermissionDeniedError') {
            setErrorMessage('마이크 사용 권한이 거부되었습니다.');
          } else {
            setErrorMessage(`마이크 오류: ${err.message}`);
          }
      } else {
           setErrorMessage('알 수 없는 마이크 접근 오류 발생');
      }
      setIsConnecting(false);
      return false;
    }
  }, [isSupported, setupWebSocket, stopAudioStream, stopRecording]); // stopRecording 추가

  // 녹음 시작 함수
  const startRecording = useCallback(async (): Promise<void> => {
    if (isRecording || isConnecting) return;

    setTranscript('');
    setErrorMessage('');
    setStatusMessage('녹음 준비 중...');

    const success = await setupAndStartStreaming();
    if (success) {
      setIsRecording(true);
      // statusMessage는 setupWebSocket 또는 setupAndStartStreaming에서 설정됨
    } else {
      // 실패 메시지는 setupAndStartStreaming 내부에서 설정됨
      setStatusMessage('녹음을 시작하지 못했습니다.'); // 최종 실패 메시지
    }
  }, [isRecording, isConnecting, setupAndStartStreaming]);

  // 컴포넌트 언마운트 시 정리
  useEffect(() => {
    return () => {
      console.log("컴포넌트 언마운트: 리소스 정리 시도");
      // null 체크 추가
      if (mediaRecorderRef.current?.state === 'recording') {
        mediaRecorderRef.current.stop();
      }
      if (webSocketRef.current?.readyState === WebSocket.OPEN) {
        webSocketRef.current.close(1000, "Component unmounted");
      }
      stopAudioStream();
      mediaRecorderRef.current = null;
      webSocketRef.current = null;
    };
  }, [stopAudioStream]);

  // 훅이 반환하는 값들 (명시적 타입 반환)
  return {
    isRecording,
    statusMessage,
    errorMessage,
    isSupported,
    isConnecting,
    transcript,
    startRecording,
    stopRecording,
  };
}
