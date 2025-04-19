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

// 전역 Window 인터페이스 확장
declare global {
  interface Window {
    webkitAudioContext?: typeof AudioContext;
  }
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
  const audioContextRef = useRef<AudioContext | null>(null);
  const audioProcessorRef = useRef<ScriptProcessorNode | null>(null);
  const playbackAudioContextRef = useRef<AudioContext | null>(null);
  const audioQueueRef = useRef<Uint8Array[]>([]);
  const isPlayingRef = useRef<boolean>(false);

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
    
    // 오디오 컨텍스트 정리
    if (audioProcessorRef.current) {
      audioProcessorRef.current.disconnect();
      audioProcessorRef.current = null;
    }
    
    if (audioContextRef.current) {
      audioContextRef.current.close();
      audioContextRef.current = null;
    }
    
    // 재생 오디오 컨텍스트 정리
    if (playbackAudioContextRef.current) {
      playbackAudioContextRef.current.close();
      playbackAudioContextRef.current = null;
    }
    
    // 오디오 큐 초기화
    audioQueueRef.current = [];
    isPlayingRef.current = false;
  }, []);

  // 녹음 중지 함수 - 먼저 정의
  const stopRecording = useCallback((): void => {
    console.log("녹음 중지 요청됨.");
    // null 체크 추가
    if (mediaRecorderRef.current?.state === 'recording') {
      mediaRecorderRef.current.stop();
    }

    if (webSocketRef.current?.readyState === WebSocket.OPEN) {
      // 1. 서버에 "disconnect" 메시지를 먼저 보냅니다.
      webSocketRef.current.send("disconnect");
      console.log("서버에 연결 종료 신호를 보냈습니다.");
      
      // 2. 잠시 후에 실제 연결을 종료합니다.
      setTimeout(() => {
        if (webSocketRef.current?.readyState === WebSocket.OPEN) {
          webSocketRef.current.close(1000, "Client stopped recording");
          console.log("WebSocket 연결 종료 요청됨.");
        }
      }, 100); // 100ms 지연
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

  // 오디오 재생 함수
  const playAudioChunk = useCallback(async (audioData: Uint8Array): Promise<void> => {
    return new Promise((resolve, reject) => { // Promise를 반환하도록 수정 (재생 완료 시 resolve)
      try {
        // --- 백엔드 TTS와 일치하는 샘플링 레이트 ---
        const SAMPLE_RATE = 24000; // 백엔드에서 설정한 값 (예: 24000)

        // 재생용 AudioContext가 없거나 닫혔으면 새로 생성 (샘플링 레이트 명시)
        if (!playbackAudioContextRef.current || playbackAudioContextRef.current.state === 'closed') {
          if (playbackAudioContextRef.current) {
            playbackAudioContextRef.current.close(); // 이전 컨텍스트 정리
          }
          playbackAudioContextRef.current = new (window.AudioContext || window.webkitAudioContext)({
            sampleRate: SAMPLE_RATE // 샘플링 레이트 지정
          });
          console.log(`Playback AudioContext 생성/재생성됨 (Sample Rate: ${SAMPLE_RATE}Hz)`);
        } else if (playbackAudioContextRef.current.sampleRate !== SAMPLE_RATE) {
            // 만약 기존 컨텍스트의 샘플링 레이트가 다르다면 (이론상 발생하기 어려움)
            console.warn(`기존 AudioContext 샘플링 레이트(${playbackAudioContextRef.current.sampleRate})와 요청된 레이트(${SAMPLE_RATE})가 다릅니다. 컨텍스트를 재생성합니다.`);
            playbackAudioContextRef.current.close();
            playbackAudioContextRef.current = new (window.AudioContext || window.webkitAudioContext)({
               sampleRate: SAMPLE_RATE
            });
        }


        const audioContext = playbackAudioContextRef.current;

        // 오디오 데이터를 AudioBuffer로 변환
        const numberOfSamples = audioData.length / 2; // LINEAR16은 샘플당 2바이트
        const audioBuffer = audioContext.createBuffer(
          1, // 모노 채널
          numberOfSamples,
          SAMPLE_RATE // 백엔드와 일치하는 샘플링 레이트 사용
        );
        const channelData = audioBuffer.getChannelData(0); // 채널 데이터 (Float32Array)

        // DataView를 사용하여 바이트 순서(little-endian)를 명시적으로 처리
        const dataView = new DataView(audioData.buffer);
        for (let i = 0; i < numberOfSamples; i++) {
          // offset: i * 2 (2바이트씩 읽음), littleEndian: true
          const int16Value = dataView.getInt16(i * 2, true);
          // Float32Array (-1.0 ~ 1.0)로 정규화
          channelData[i] = int16Value / 32768.0;
        }

        // 오디오 소스 생성 및 재생
        const source = audioContext.createBufferSource();
        source.buffer = audioBuffer;
        source.connect(audioContext.destination);

        // 재생 완료 시 Promise를 resolve하고 소스 정리
        source.onended = () => {
          console.log(`오디오 청크 재생 완료 (${audioData.length} bytes)`);
          source.disconnect();
          resolve(); // Promise 완료 알림
        };

        source.start(0); // 즉시 재생

      } catch (error) {
        console.error('오디오 재생 함수 내 오류 발생:', error);
        // 오류 발생 시 재생 상태 초기화 등 고려
        isPlayingRef.current = false; // 재생 실패 시 상태 업데이트
        reject(error); // Promise 실패 알림
      }
    }); // Promise 종료
  }, []); // 의존성 배열 비우기 (내부에서 사용하는 상태/ref는 의존성이 아님)

  // 오디오 큐 처리 함수 (재생 완료를 기다리도록 수정)
  const processAudioQueue = useCallback(async (): Promise<void> => {
      // 이미 재생 중이거나 큐가 비었으면 반환
      if (isPlayingRef.current || audioQueueRef.current.length === 0) return;

      isPlayingRef.current = true; // 재생 시작 플래그 설정
      console.log("오디오 큐 처리 시작...");

      // 큐에 있는 모든 오디오 데이터를 순차적으로 재생
      while (audioQueueRef.current.length > 0) {
        const audioData = audioQueueRef.current.shift(); // 큐에서 하나 꺼냄
        if (audioData) {
          try {
            console.log(`다음 오디오 청크 재생 시도 (${audioData.length} bytes)...`);
            // playAudioChunk가 반환하는 Promise를 기다려서 재생이 완료될 때까지 대기
            await playAudioChunk(audioData);
            console.log("이전 오디오 청크 재생 완료.");
          } catch (error) {
              console.error("오디오 큐 처리 중 playAudioChunk 오류:", error);
              // 오류 발생 시 큐 처리 중단 또는 계속 진행 결정
              // 여기서는 일단 중단하고 재생 상태 해제
              isPlayingRef.current = false;
              console.log("오디오 큐 처리 중 오류로 인해 중단됨.");
              return; // 함수 종료
          }
        }
      }

      // 모든 큐 처리가 성공적으로 완료되면 재생 상태 해제
      isPlayingRef.current = false;
      console.log("오디오 큐 처리 완료.");
  }, [playAudioChunk]); // playAudioChunk 함수에 의존

  // WebSocket 연결 설정 함수
  const setupWebSocket = useCallback((): Promise<WebSocket> => {
    return new Promise((resolve, reject) => {
      if (webSocketRef.current && webSocketRef.current.readyState !== WebSocket.CLOSED) {
        webSocketRef.current.close();
        console.log("Previous WebSocket connection closed.");
      }

      const ws = new WebSocket(WEBSOCKET_URL);
      ws.binaryType = 'arraybuffer'; // 바이너리 타입을 arraybuffer로 설정 (PCM 데이터 전송용)

      ws.onopen = () => {
        console.log('WebSocket 연결 성공');
        setStatusMessage('연결됨. 녹음 중...');
        setIsConnecting(false);
        webSocketRef.current = ws;
        resolve(ws);
      };

      // 메시지 수신 처리 (타입 명시: MessageEvent)
      ws.onmessage = (event: MessageEvent) => {
         // 서버에서 텍스트(JSON) 또는 바이너리 데이터를 보낼 수 있으므로 타입 확인
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
        } else if (event.data instanceof ArrayBuffer) {
             // 서버에서 오디오 데이터를 보낸 경우의 처리 (TTS 결과 재생)
             console.log('WebSocket 바이너리 메시지 수신:', event.data.byteLength, 'bytes');
             
             // 오디오 데이터를 큐에 추가
             const audioData = new Uint8Array(event.data);
             audioQueueRef.current.push(audioData);
             
             // 오디오 큐 처리 시작
             processAudioQueue();
        } else if (event.data instanceof Blob) {
             // Blob 데이터를 ArrayBuffer로 변환하여 처리
             event.data.arrayBuffer().then(buffer => {
                console.log('WebSocket Blob 메시지 수신:', buffer.byteLength, 'bytes');
                
                // 오디오 데이터를 큐에 추가
                const audioData = new Uint8Array(buffer);
                audioQueueRef.current.push(audioData);
                
                // 오디오 큐 처리 시작
                processAudioQueue();
             }).catch(error => {
                console.error('Blob 처리 중 오류 발생:', error);
             });
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
  }, [stopAudioStream, processAudioQueue]); // processAudioQueue 의존성 추가

  // MediaRecorder 설정 및 스트리밍 시작 함수
  const setupAndStartStreaming = useCallback(async (): Promise<boolean> => {
    if (!isSupported) {
      setErrorMessage('마이크 녹음 또는 WebSocket을 지원하지 않는 브라우저입니다.');
      return false;
    }

    try {
      // 오디오 스트림 가져오기
      const stream: MediaStream = await navigator.mediaDevices.getUserMedia({ 
        audio: {
          channelCount: 1, // 모노 채널
          sampleRate: 16000, // 16kHz 샘플링 레이트
          echoCancellation: true,
          noiseSuppression: true,
          autoGainControl: true
        } 
      });
      audioStreamRef.current = stream;

      // WebSocket 연결 설정
      setIsConnecting(true);
      setStatusMessage('WebSocket 연결 중...');
      await setupWebSocket();

      if (webSocketRef.current?.readyState !== WebSocket.OPEN) {
        console.error("WebSocket 연결 실패하여 녹음을 시작할 수 없습니다.");
        stopAudioStream();
        return false;
      }

      // Web Audio API를 사용하여 LINEAR16 PCM 데이터 생성
      const audioContext = new (window.AudioContext || window.webkitAudioContext)({
        sampleRate: 16000 // 16kHz 샘플링 레이트
      });
      audioContextRef.current = audioContext;

      const source = audioContext.createMediaStreamSource(stream);
      const processor = audioContext.createScriptProcessor(4096, 1, 1);
      audioProcessorRef.current = processor;

      // 오디오 처리 및 전송
      processor.onaudioprocess = (e) => {
        if (webSocketRef.current?.readyState === WebSocket.OPEN) {
          // 입력 버퍼에서 데이터 가져오기
          const inputData = e.inputBuffer.getChannelData(0);
          
          // Float32Array를 Int16Array로 변환 (LINEAR16 형식)
          const pcmData = new Int16Array(inputData.length);
          for (let i = 0; i < inputData.length; i++) {
            // Float32Array (-1.0 ~ 1.0)를 Int16Array (-32768 ~ 32767)로 변환
            pcmData[i] = Math.max(-32768, Math.min(32767, Math.floor(inputData[i] * 32767)));
          }
          
          // WebSocket으로 전송
          webSocketRef.current.send(pcmData.buffer);
        }
      };

      // 오디오 노드 연결
      source.connect(processor);
      processor.connect(audioContext.destination);

      console.log(`녹음 및 스트리밍 시작 (LINEAR16 PCM, 16kHz, 모노)`);
      return true;

    } catch (err) {
      console.error('마이크 접근 또는 오디오 처리 설정 오류:', err);
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
    setIsRecording(true);
    setStatusMessage('녹음 준비 중...');

    const success = await setupAndStartStreaming();
    if (!success) {
      setIsRecording(false);
      setStatusMessage('녹음 시작 실패. 다시 시도하세요.');
    }
  }, [isRecording, isConnecting, setupAndStartStreaming]);

  // 컴포넌트 언마운트 시 정리
  useEffect(() => {
    return () => {
      stopRecording();
    };
  }, [stopRecording]);

  // 반환 객체
  return {
    isRecording,
    statusMessage,
    errorMessage,
    isSupported,
    isConnecting,
    transcript,
    startRecording,
    stopRecording
  };
}
