import { useState, useEffect, useRef, useCallback } from 'react';
// import axios from 'axios'; // 사용하지 않으므로 제거
import { useAudio } from '../contexts/AudioContext';

// 사용하지 않으므로 제거
// interface AudioChunk {
//   type: 'audio';
//   data: string; // Base64 encoded audio data
// }

// WebSocket 연결 주소를 환경 변수에서 가져옴
// .env 파일에 VITE_BACKEND_WS_URL=ws://localhost:8000/ws/audio 형태로 정의해야 합니다.
const WEBSOCKET_URL = import.meta.env.VITE_BACKEND_WS_URL;

// WebSocket 서버로부터 받을 것으로 예상되는 데이터 구조 인터페이스
interface WebSocketResponse {
  transcript?: string;
  is_final?: boolean;
  error?: string; // 백엔드 에러 메시지 필드 (선택 사항)
  control?: string;
  action?: string;
  reason?: string;
  message?: string;
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
  isMicDisabled: boolean;
  micStatusMessage: string;
  processingTime: number | null;
  isPlayingAudio: boolean;
  lastAudioData: Float32Array | null;
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
  // isInitialized 가져오기
  const { processingAudio, clearAudio, analyserNode, audioContext, isInitialized } = useAudio();

  // 기존 로그 제거 또는 수정
  console.log('[useVoiceStreaming] Context status:', {
    isInitialized,
    isAudioPlaying: useAudio().isAudioPlaying, // isAudioPlaying은 state이므로 매번 최신 값 확인
    analyserNode: !!analyserNode,
    audioContext: !!audioContext
  });

  // 상태 변수들 (타입 명시)
  const [isRecording, setIsRecording] = useState<boolean>(false);
  const [statusMessage, setStatusMessage] = useState<string>('버튼을 누르고 말씀하세요.');
  const [errorMessage, setErrorMessage] = useState<string>('');
  const [isSupported, setIsSupported] = useState<boolean>(false);
  const [isConnecting, setIsConnecting] = useState<boolean>(false);
  const [transcript, setTranscript] = useState<string>('');
  const [isMicDisabled, setIsMicDisabled] = useState<boolean>(false);
  const [micStatusMessage, setMicStatusMessage] = useState<string>('');
  const [processingTime, setProcessingTime] = useState<number | null>(null);
  const [isPlayingAudio, setIsPlayingAudio] = useState<boolean>(false);
  const [lastAudioData, setLastAudioData] = useState<Float32Array | null>(null);

  // useRef (타입 명시, 초기값 null)
  const mediaRecorderRef = useRef<MediaRecorder | null>(null);
  const webSocketRef = useRef<WebSocket | null>(null);
  const audioStreamRef = useRef<MediaStream | null>(null);
  const audioProcessorRef = useRef<ScriptProcessorNode | null>(null);
  const audioQueueRef = useRef<Uint8Array[]>([]);
  const isPlayingRef = useRef<boolean>(false);

  // 마이크 활성화 대기 플래그 추가
  const pendingMicEnableRef = useRef<boolean>(false);
  const pendingMicMessageRef = useRef<string>('');

  // 추가할 상태 변수들
  const micDisabledTimeRef = useRef<number | null>(null);
  const isFirstAudioChunkRef = useRef<boolean>(true);

  // 브라우저 지원 여부 확인
  useEffect(() => {
    setIsSupported(!!(navigator.mediaDevices && typeof navigator.mediaDevices.getUserMedia === 'function' && window.WebSocket));
  }, []);

  // 마이크 활성화 함수를 먼저 선언
  const enableMicrophone = useCallback((message: string) => {
    if (audioStreamRef.current) {
      setTimeout(() => {
        if (audioStreamRef.current) {
          /* AEC가 적용되어 있으므로 트랙 활성화는 더 이상 필요 없음
          audioStreamRef.current.getAudioTracks().forEach(track => {
            track.enabled = true;
          });
          */
          console.log('마이크 상태가 활성화로 변경되었습니다 (AEC로 이미 처리 중)');
          setIsMicDisabled(false); // 상태만 변경
          setMicStatusMessage('');
          setStatusMessage(message);
          
          // 마이크가 다시 활성화될 때 시간 측정 변수 초기화
          // 주의: processingTime은 초기화하지 않고 유지 (화면에 계속 표시)
          micDisabledTimeRef.current = null;
          isFirstAudioChunkRef.current = true;
        }
        pendingMicEnableRef.current = false;
      }, 300);
    }
  }, []);

  // WebRTC 루프백 연결을 설정하여 에코 캔슬레이션 강화
  const setupEchoCancellationLoopback = useCallback(async (): Promise<void> => {
    // 오디오 컨텍스트가 준비되지 않았다면 무시
    if (!audioContext) {
      console.log("AudioContext가 준비되지 않아 에코 캔슬레이션 루프백을 설정할 수 없습니다.");
      return;
    }

    try {
      console.log("에코 캔슬레이션 루프백 연결 설정 중...");

      // 로컬 WebRTC 연결 생성
      const peerConnection1 = new RTCPeerConnection();
      const peerConnection2 = new RTCPeerConnection();

      // 이벤트 핸들러 설정
      peerConnection1.onicecandidate = (event) => {
        if (event.candidate) {
          peerConnection2.addIceCandidate(event.candidate).catch(console.error);
        }
      };

      peerConnection2.onicecandidate = (event) => {
        if (event.candidate) {
          peerConnection1.addIceCandidate(event.candidate).catch(console.error);
        }
      };

      // 오디오 출력을 MediaStreamTrack으로 변환
      if (audioStreamRef.current) {
        // 오디오 입력 스트림을 루프백 연결에 추가
        audioStreamRef.current.getAudioTracks().forEach(track => {
          peerConnection1.addTrack(track, audioStreamRef.current!);
        });

        // 미디어 스트림 대상 생성
        const destination = audioContext.createMediaStreamDestination();
        
        // 현재 Web Audio 노드를 대상 노드에 연결
        if (analyserNode) {
          analyserNode.connect(destination);
          console.log("AnalyserNode를 루프백 대상에 연결했습니다.");
        }
      }

      // peerConnection2에서 오디오 트랙을 수신하기 위한 이벤트 설정
      peerConnection2.ontrack = () => {
        console.log("루프백 연결을 통해 오디오 트랙을 받았습니다.");
        // 여기서 추가 처리가 필요하다면 구현
      };

      // SDP 교환 - Offer 생성
      const offer = await peerConnection1.createOffer();
      await peerConnection1.setLocalDescription(offer);
      await peerConnection2.setRemoteDescription(offer);

      // Answer 생성
      const answer = await peerConnection2.createAnswer();
      await peerConnection2.setLocalDescription(answer);
      await peerConnection1.setRemoteDescription(answer);

      console.log("에코 캔슬레이션 루프백 연결이 설정되었습니다.");

      // 연결 객체 참조 저장 (나중에 정리할 수 있도록)
      // 객체를 저장할 Ref를 추가할 수 있음

    } catch (error) {
      console.error("에코 캔슬레이션 루프백 설정 중 오류:", error);
    }
  }, [audioContext, analyserNode]);

  // 오디오 스트림 중지 함수 - clearAudio 호출 추가
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
    
    // 오디오 큐 초기화
    audioQueueRef.current = [];
    isPlayingRef.current = false;

    // AudioContext 상태 초기화 호출
    clearAudio();
    console.log("[stopAudioStream] clearAudio 호출됨");
  }, [clearAudio]); // clearAudio 의존성 추가

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

  // 오디오 재생 함수 수정
  const playAudioChunk = useCallback(async (audioData: Uint8Array): Promise<void> => {
    // *** 초기화 및 컨텍스트 유효성 검사 강화 ***
    if (!isInitialized || !audioContext) {
      console.error(`AudioContext not ready. Initialized: ${isInitialized}, Context available: ${!!audioContext}`);
      return Promise.reject('AudioContext is not ready or available');
    }
    // ***************************************

    // AudioContext 상태 확인 및 재개 (필요한 경우)
    if (audioContext.state === 'suspended') {
      await audioContext.resume();
      console.log("AudioContext resumed.");
    }

    return new Promise((resolve, reject) => {
      try {
        // 오디오 데이터 로깅 추가
        console.log('오디오 데이터 전달 시도:', {
          byteLength: audioData.byteLength,
          isValidArray: audioData instanceof Uint8Array,
          isEmpty: audioData.length === 0,
          firstFewBytes: Array.from(audioData.slice(0, 10))
        });

        processingAudio(); // 오디오 처리 시작 알림

        // 첫 번째 오디오 청크인 경우 처리 시간 계산
        if (isFirstAudioChunkRef.current && micDisabledTimeRef.current !== null) {
          const firstAudioTime = Date.now();
          const timeTaken = (firstAudioTime - micDisabledTimeRef.current) / 1000; // 초 단위로 변환
          setProcessingTime(timeTaken);
          console.log(`첫 오디오 재생까지 소요 시간: ${timeTaken.toFixed(2)}초`);
          isFirstAudioChunkRef.current = false;
        }

        // --- decodeAudioData 대신 수동으로 AudioBuffer 생성 ---
        const numberOfSamples = audioData.byteLength / 2; // 16-bit PCM = 2 bytes per sample
        const sampleRate = audioContext.sampleRate; // Provider에서 설정한 24000Hz 사용

        if (numberOfSamples <= 0) {
             console.warn("Received empty audio data.");
             resolve(); // 빈 데이터는 그냥 완료 처리
             return;
        }

        const audioBuffer = audioContext.createBuffer(
          1, // numberOfChannels - 모노
          numberOfSamples,
          sampleRate
        );

        const channelData = audioBuffer.getChannelData(0); // Float32Array
        const dataView = new DataView(audioData.buffer);

        for (let i = 0; i < numberOfSamples; i++) {
          // LINEAR16 (signed 16-bit integer, little-endian)
          const int16Value = dataView.getInt16(i * 2, true);
          // Normalize to Float32 range (-1.0 to 1.0)
          channelData[i] = int16Value / 32768.0;
        }
        // --- 오디오 데이터 상태 업데이트 추가 ---
        setLastAudioData(channelData);
        // ------------------------------------

        // 수동으로 생성된 AudioBuffer를 사용하여 소스 노드 생성
        const source = audioContext.createBufferSource();
        source.buffer = audioBuffer; // 직접 생성한 버퍼 할당

        // AnalyserNode 또는 destination에 연결
        if (analyserNode) {
            source.connect(analyserNode);
            // Provider에서 AnalyserNode를 destination에 미리 연결했으므로,
            // 여기서는 source -> analyser 연결만 하면 됨.
            console.log('Audio source connected to AnalyserNode.');
        } else {
            // AnalyserNode 없으면 바로 destination 연결
            source.connect(audioContext.destination);
            console.warn('AnalyserNode not available, connecting source directly to destination.');
        }

        console.log(`오디오 청크 재생 시작 (Manually created buffer, ${numberOfSamples} samples)`);

        source.onended = () => {
          console.log(`오디오 청크 재생 완료 (Manually created buffer)`);
          try {
              source.disconnect(); // 연결 해제 시도
          } catch (disconnectError) {
              // 이미 연결 해제된 경우 오류 발생 가능성 있음
              console.warn("Error disconnecting source node (might already be disconnected):", disconnectError);
          }
          resolve();
        };

        source.start(0); // 즉시 재생

      } catch (error) {
        console.error('오디오 재생 함수 내 오류 발생:', error);
        reject(error);
      }
    });
  // isInitialized 의존성 추가
  }, [processingAudio, audioContext, analyserNode, isInitialized]);

  // 그 다음에 processAudioQueue 함수 선언 - clearAudio 호출 추가
  const processAudioQueue = useCallback(async (): Promise<void> => {
    if (isPlayingRef.current || audioQueueRef.current.length === 0) return;

    isPlayingRef.current = true;
    setIsPlayingAudio(true); // UI 상태 업데이트: 재생 시작
    console.log(`오디오 큐 처리 시작... (${audioQueueRef.current.length}개 항목)`);

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
            setIsPlayingAudio(false); // UI 상태 업데이트: 재생 중지 (오류)
            clearAudio(); // 오류 시에도 상태 초기화
            console.log("오디오 큐 처리 중 오류로 인해 중단 및 clearAudio 호출됨.");
            return; // 함수 종료
        }
      }
    }

    // 모든 큐 처리가 성공적으로 완료되면 재생 상태 해제
    isPlayingRef.current = false;
    setIsPlayingAudio(false); // UI 상태 업데이트: 재생 중지 (완료)
    clearAudio(); // 모든 오디오 재생 완료 후 상태 초기화
    console.log("오디오 큐 처리 완료 및 clearAudio 호출됨.");

    if (pendingMicEnableRef.current) {
      console.log("모든 오디오 재생 완료 후 마이크 활성화 실행");
      enableMicrophone(pendingMicMessageRef.current);
    }
  }, [playAudioChunk, enableMicrophone, clearAudio]); // clearAudio 의존성 추가

  // WebSocket 연결 설정 함수
  const setupWebSocket = useCallback((): Promise<WebSocket> => {
    return new Promise((resolve, reject) => {
      if (!WEBSOCKET_URL) {
          const errMsg = "WebSocket URL이 정의되지 않았습니다. .env 파일에 VITE_BACKEND_WS_URL을 설정해주세요.";
          console.error(errMsg);
          setErrorMessage(errMsg);
          setIsConnecting(false); // 연결 시도 중 상태 해제
          reject(new Error(errMsg));
          return;
      }

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
                const data = JSON.parse(event.data) as WebSocketResponse;
                
                // 마이크 제어 메시지 처리
                if (data.control === 'mic_status') {
                  if (data.action === 'disable') {
                    // 마이크 비활성화 시간 기록
                    if (audioStreamRef.current) {
                      console.log('마이크 비활성화 요청을 받았지만, AEC 기능으로 처리됨:', data.reason);
                      /* 마이크 비활성화 코드 주석 처리 - AEC로 대체
                      audioStreamRef.current.getAudioTracks().forEach(track => {
                        track.enabled = false;
                      });
                      setIsMicDisabled(true);
                      */
                      
                      // 상태 메시지는 업데이트
                      setMicStatusMessage(data.message || 'AI가 응답 중입니다...');
                      setStatusMessage(data.message || 'AI가 응답 중입니다...');
                      
                      // 마이크 비활성화 시간 기록
                      micDisabledTimeRef.current = Date.now();
                      isFirstAudioChunkRef.current = true; // 첫 오디오 플래그 초기화
                    }
                  } else if (data.action === 'enable') {
                    // 마이크 활성화 요청을 즉시 처리하지 않고 플래그로 저장
                    console.log('마이크 활성화 요청 받음 - 오디오 재생 완료 후 처리 예정:', data.reason);
                    pendingMicEnableRef.current = true;
                    pendingMicMessageRef.current = data.message || '말씀하세요...';
                    
                    // 오디오 큐가 비어있는 경우에만 즉시 활성화
                    if (audioQueueRef.current.length === 0 && !isPlayingRef.current) {
                      enableMicrophone(pendingMicMessageRef.current);
                    } else {
                      console.log(`아직 ${audioQueueRef.current.length}개의 오디오가 큐에 있고, 재생 중 상태: ${isPlayingRef.current}`);
                    }
                  }
                }
                
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
             } catch (e) {
                console.error('JSON 파싱 오류:', e);
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
  }, [stopAudioStream, processAudioQueue, stopRecording, enableMicrophone]); // enableMicrophone, stopRecording, processAudioQueue 의존성 추가

  // MediaRecorder 설정 및 스트리밍 시작 함수
  const setupAndStartStreaming = useCallback(async (): Promise<boolean> => {
    if (!isSupported) {
      setErrorMessage('마이크 녹음 또는 WebSocket을 지원하지 않는 브라우저입니다.');
      return false;
    }

    // *** 녹음용 AudioContext는 별도로 관리 ***
    let recordingAudioContext: AudioContext | null = null;
    let recordingProcessor: ScriptProcessorNode | null = null;
    // **************************************

    try {
      // 오디오 스트림 가져오기
      const stream: MediaStream = await navigator.mediaDevices.getUserMedia({
        audio: {
          channelCount: 1, 
          sampleRate: 16000,
          // 에코 제거 설정 강화
          echoCancellation: {
            exact: true // exact 설정으로 확실히 활성화
          },
          noiseSuppression: true,
          autoGainControl: true
        }
      });
      audioStreamRef.current = stream;

      // 스피커 출력 트랙이 사용 가능한지 확인하고 WebRTC 루프백 연결을 생성하여 에코 캔슬링 강화
      await setupEchoCancellationLoopback();

      // WebSocket 연결 설정
      setIsConnecting(true);
      setStatusMessage('WebSocket 연결 중...');
      await setupWebSocket();

      if (webSocketRef.current?.readyState !== WebSocket.OPEN) {
        console.error("WebSocket 연결 실패하여 녹음을 시작할 수 없습니다.");
        stopAudioStream(); // 스트림 정리
        return false;
      }

      // Web Audio API를 사용하여 LINEAR16 PCM 데이터 생성 (녹음용 컨텍스트 사용)
      recordingAudioContext = new (window.AudioContext || window.webkitAudioContext)({
        sampleRate: 16000 // 녹음은 16kHz
      });
      // audioContextRef.current = recordingAudioContext; // 전역 audioContextRef는 재생용으로 유지

      const source = recordingAudioContext.createMediaStreamSource(stream);
      recordingProcessor = recordingAudioContext.createScriptProcessor(4096, 1, 1);
      audioProcessorRef.current = recordingProcessor; // ScriptProcessor 참조 저장 (정리용)

      // 오디오 처리 및 전송
      recordingProcessor.onaudioprocess = (e) => {
        if (webSocketRef.current?.readyState === WebSocket.OPEN) {
          const inputData = e.inputBuffer.getChannelData(0);
          const pcmData = new Int16Array(inputData.length);
          for (let i = 0; i < inputData.length; i++) {
            pcmData[i] = Math.max(-32768, Math.min(32767, Math.floor(inputData[i] * 32767)));
          }
          webSocketRef.current.send(pcmData.buffer);
        }
      };

      // 오디오 노드 연결 (녹음용 컨텍스트 내에서)
      source.connect(recordingProcessor);
      recordingProcessor.connect(recordingAudioContext.destination); // 이 연결은 소리가 나지 않게 함

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

      // *** 오류 발생 시 녹음용 컨텍스트 정리 ***
      if (recordingProcessor) recordingProcessor.disconnect();
      if (recordingAudioContext) recordingAudioContext.close();
      // **************************************

      return false;
    }
  // setupWebSocket, stopAudioStream 의존성 유지
  }, [isSupported, setupWebSocket, stopAudioStream, setupEchoCancellationLoopback]);

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

  // 추가: 컴포넌트 언마운트 시 정리
  useEffect(() => {
    return () => {
      // 컴포넌트 언마운트 시 플래그 초기화
      pendingMicEnableRef.current = false;
    };
  }, []);

  // 반환 객체
  return {
    isRecording,
    statusMessage,
    errorMessage,
    isSupported,
    isConnecting,
    transcript,
    startRecording,
    stopRecording,
    isMicDisabled,
    micStatusMessage,
    processingTime,
    isPlayingAudio,
    lastAudioData,
  };
}
