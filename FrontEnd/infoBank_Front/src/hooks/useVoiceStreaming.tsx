import { useState, useEffect, useRef, useCallback } from 'react';
import { useAudio } from '../contexts/AudioContext';
import { UseVoiceStreamingReturn } from '../types/voiceStreamingTypes';
import { convertFloat32ToPCM, ensureAudioContextReady } from '../utils/audioUtils';
import { parseWebSocketMessage, processEmotionResult, isInterruptionSignal, processResponseStatus } from '../utils/webSocketUtils';

// WebSocket 연결 주소를 환경 변수에서 가져옴
const WEBSOCKET_URL = import.meta.env.VITE_BACKEND_WS_URL;

// 전역 Window 인터페이스 확장 (직접 선언)
declare global {
  interface Window {
    webkitAudioContext?: typeof AudioContext;
  }
}

/**
 * AI 음성 대화 스트리밍을 위한 커스텀 훅
 * @returns {UseVoiceStreamingReturn} 음성 스트리밍 관련 상태 및 제어 함수
 */
export function useVoiceStreaming(): UseVoiceStreamingReturn {
  // isInitialized 가져오기
  const { processingAudio, clearAudio, analyserNode, audioContext, isInitialized } = useAudio();

  // 로그
  console.log('[useVoiceStreaming] Context status:', {
    isInitialized,
    isAudioPlaying: useAudio().isAudioPlaying,
    analyserNode: !!analyserNode,
    audioContext: !!audioContext
  });

  // 상태 변수들
  const [isRecording, setIsRecording] = useState<boolean>(false);
  const [statusMessage, setStatusMessage] = useState<string>('버튼을 누르고 말씀하세요.');
  const [errorMessage, setErrorMessage] = useState<string>('');
  const [isSupported, setIsSupported] = useState<boolean>(false);
  const [isConnecting, setIsConnecting] = useState<boolean>(false);
  const [transcript, setTranscript] = useState<string>('');
  const [isResponseProcessing, setIsResponseProcessing] = useState<boolean>(false);
  const [responseStatusMessage, setResponseStatusMessage] = useState<string>('');
  const [processingTime, setProcessingTime] = useState<number | null>(null);
  const [isPlayingAudio, setIsPlayingAudio] = useState<boolean>(false);
  const [lastAudioData, setLastAudioData] = useState<Float32Array | null>(null);
  const [currentEmotion, setCurrentEmotion] = useState<string>("중립");

  // useRef
  const mediaRecorderRef = useRef<MediaRecorder | null>(null);
  const webSocketRef = useRef<WebSocket | null>(null);
  const audioStreamRef = useRef<MediaStream | null>(null);
  const audioProcessorRef = useRef<ScriptProcessorNode | null>(null);
  const audioQueueRef = useRef<Uint8Array[]>([]);
  const isPlayingRef = useRef<boolean>(false);
  const pendingResponseEnableRef = useRef<boolean>(false);
  const pendingResponseMessageRef = useRef<string>('');
  const responseStartTimeRef = useRef<number | null>(null);
  const isFirstAudioChunkRef = useRef<boolean>(true);
  const activeSourceNodes = useRef<AudioBufferSourceNode[]>([]);
  
  // 브라우저 지원 여부 확인
  useEffect(() => {
    setIsSupported(!!(navigator.mediaDevices && typeof navigator.mediaDevices.getUserMedia === 'function' && window.WebSocket));
  }, []);

  // 응답 처리 종료 함수
  const enableResponseProcessing = useCallback((message: string) => {
    if (audioStreamRef.current) {
      setTimeout(() => {
        if (audioStreamRef.current) {
          console.log('응답 처리가 종료되었습니다');
          setIsResponseProcessing(false);
          setResponseStatusMessage('');
          setStatusMessage(message);
          
          // 응답 처리가 종료될 때 시간 측정 변수 초기화
          responseStartTimeRef.current = null;
          isFirstAudioChunkRef.current = true;
        }
        pendingResponseEnableRef.current = false;
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
          peerConnection2.addIceCandidate(event.candidate)
            .catch(err => console.error("ICE candidate 추가 실패:", err));
        }
      };

      peerConnection2.onicecandidate = (event) => {
        if (event.candidate) {
          peerConnection1.addIceCandidate(event.candidate)
            .catch(err => console.error("ICE candidate 추가 실패:", err));
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
    } catch (error) {
      console.error("에코 캔슬레이션 루프백 설정 중 오류:", error);
    }
  }, [audioContext, analyserNode]);

  // 오디오 스트림 중지 함수
  const stopAudioStream = useCallback((): void => {
    if (audioStreamRef.current) {
      audioStreamRef.current.getTracks().forEach(track => track.stop());
      console.log("오디오 스트림 중지됨");
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

    // AudioContext 상태 초기화
    clearAudio();
    console.log("clearAudio 호출됨");
  }, [clearAudio]);

  // 녹음 중지 함수
  const stopRecording = useCallback((): void => {
    console.log("녹음 중지 요청됨");
    
    if (mediaRecorderRef.current?.state === 'recording') {
      mediaRecorderRef.current.stop();
    }

    if (webSocketRef.current?.readyState === WebSocket.OPEN) {
      // 서버에 연결 종료 신호 전송
      webSocketRef.current.send("disconnect");
      console.log("서버에 연결 종료 신호를 보냈습니다");
      
      // 지연 후 실제 연결 종료
      setTimeout(() => {
        if (webSocketRef.current?.readyState === WebSocket.OPEN) {
          webSocketRef.current.close(1000, "Client stopped recording");
          console.log("WebSocket 연결 종료 요청됨");
        }
      }, 100);
    } else {
      // WebSocket이 없거나 이미 닫혔으면 스트림만 정리
      stopAudioStream();
    }

    // 상태 업데이트
    setIsRecording(false);
    setStatusMessage('버튼을 누르고 말씀하세요.');
    mediaRecorderRef.current = null;
  }, [stopAudioStream]);

  // 인터럽션 감지 핸들러
  const handleInterruption = useCallback(() => {
    console.log('인터럽션 감지됨, 오디오 재생 중단');
    
    // 모든 활성 소스 노드 중지
    activeSourceNodes.current.forEach(node => {
      try {
        node.stop();
      } catch {
        // 이미 중지된 노드는 무시
      }
    });
    
    // 배열 초기화
    activeSourceNodes.current = [];
    
    // 오디오 큐 비우기
    audioQueueRef.current = [];
    
    clearAudio();
    setCurrentEmotion("중립");
    console.log('인터럽션 처리 완료, 감정 상태를 "중립"으로 재설정');
  }, [clearAudio]);

  // 오디오 재생 함수
  const playAudioChunk = useCallback(async (audioData: Uint8Array): Promise<void> => {
    // 초기화 및 컨텍스트 유효성 검사
    if (!isInitialized || !audioContext) {
      console.error(`AudioContext not ready. Initialized: ${isInitialized}, Context available: ${!!audioContext}`);
      return Promise.reject('AudioContext is not ready or available');
    }

    // AudioContext 상태 확인 및 재개
    const isReady = await ensureAudioContextReady(audioContext);
    if (!isReady) {
      return Promise.reject('Failed to resume AudioContext');
    }

    return new Promise((resolve, reject) => {
      try {
        // 오디오 데이터 로깅
        console.log('오디오 데이터 전달 시도:', {
          byteLength: audioData.byteLength,
          isValidArray: audioData instanceof Uint8Array,
          isEmpty: audioData.length === 0,
          firstFewBytes: Array.from(audioData.slice(0, 10))
        });

        processingAudio(); // 오디오 처리 시작 알림

        // 첫 번째 오디오 청크인 경우 처리 시간 계산
        if (isFirstAudioChunkRef.current && responseStartTimeRef.current !== null) {
          const firstAudioTime = Date.now();
          const timeTaken = (firstAudioTime - responseStartTimeRef.current) / 1000; // 초 단위로 변환
          setProcessingTime(timeTaken);
          console.log(`첫 오디오 재생까지 소요 시간: ${timeTaken.toFixed(2)}초`);
          isFirstAudioChunkRef.current = false;
        }

        // AudioBuffer 생성
        const numberOfSamples = audioData.byteLength / 2; // 16-bit PCM = 2 bytes per sample
        const sampleRate = audioContext.sampleRate;

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

        // LINEAR16 데이터를 Float32Array로 변환
        for (let i = 0; i < numberOfSamples; i++) {
          // LINEAR16 (signed 16-bit integer, little-endian)
          const int16Value = dataView.getInt16(i * 2, true);
          // Normalize to Float32 range (-1.0 to 1.0)
          channelData[i] = int16Value / 32768.0;
        }
        
        // 오디오 데이터 상태 업데이트
        setLastAudioData(channelData);

        // 소스 노드 생성 및 연결
        const sourceNode = audioContext.createBufferSource();
        sourceNode.buffer = audioBuffer;
        
        // analyserNode 연결
        if (analyserNode) {
          sourceNode.connect(analyserNode);
          console.log('Audio source connected to AnalyserNode.');
        } else {
          sourceNode.connect(audioContext.destination);
          console.warn('AnalyserNode not available, connecting source directly to destination.');
        }
        
        // 활성 소스 노드 목록에 추가
        activeSourceNodes.current.push(sourceNode);
        
        // 재생 완료 시 처리 로직
        sourceNode.onended = () => {
          console.log('오디오 청크 재생 완료');
          
          // 배열에서 해당 노드 제거
          const index = activeSourceNodes.current.indexOf(sourceNode);
          if (index > -1) {
            activeSourceNodes.current.splice(index, 1);
          }
          
          resolve();
        };
        
        // 재생 시작
        sourceNode.start();
        console.log(`오디오 청크 재생 시작 (${numberOfSamples} samples)`);
        
        // 오디오 재생 중임을 설정
        if (processingAudio) {
          processingAudio();
        }
      } catch (error) {
        console.error('오디오 처리 중 오류:', error);
        reject(error);
      }
    });
  }, [processingAudio, audioContext, analyserNode, isInitialized]);

  // 오디오 큐 처리 함수
  const processAudioQueue = useCallback(async (): Promise<void> => {
    if (isPlayingRef.current || audioQueueRef.current.length === 0) return;

    isPlayingRef.current = true;
    setIsPlayingAudio(true); // UI 상태 업데이트: 재생 시작
    console.log(`오디오 큐 처리 시작... (${audioQueueRef.current.length}개 항목)`);

    try {
      // 큐에 있는 모든 오디오 데이터를 순차적으로 재생
      while (audioQueueRef.current.length > 0) {
        const audioData = audioQueueRef.current.shift();
        if (audioData) {
          try {
            console.log(`다음 오디오 청크 재생 시도 (${audioData.length} bytes)...`);
            // 재생이 완료될 때까지 대기
            await playAudioChunk(audioData);
            console.log("오디오 청크 재생 완료");
          } catch (error) {
            console.error("오디오 재생 중 오류:", error);
            throw error; // 상위 try-catch로 전달
          }
        }
      }
      
      console.log("모든 오디오 청크 재생 완료");
    } catch (error) {
      console.error("오디오 큐 처리 중 오류:", error);
    } finally {
      // 재생 상태 및 상태 초기화
      isPlayingRef.current = false;
      setIsPlayingAudio(false);
      clearAudio();
      setCurrentEmotion("중립");
      console.log("오디오 큐 처리 완료 및 감정 상태를 '중립'으로 재설정");
      
      // 응답 처리 종료 확인
      if (pendingResponseEnableRef.current) {
        console.log("모든 오디오 재생 완료 후 응답 처리 종료 실행");
        enableResponseProcessing(pendingResponseMessageRef.current);
      }
    }
  }, [playAudioChunk, enableResponseProcessing, clearAudio]);

  // WebSocket 연결 설정 함수
  const setupWebSocket = useCallback((): Promise<WebSocket> => {
    return new Promise((resolve, reject) => {
      if (!WEBSOCKET_URL) {
        const errMsg = "WebSocket URL이 정의되지 않았습니다. .env 파일에 VITE_BACKEND_WS_URL을 설정해주세요.";
        console.error(errMsg);
        setErrorMessage(errMsg);
        setIsConnecting(false);
        reject(new Error(errMsg));
        return;
      }

      // 기존 연결이 있으면 닫기
      if (webSocketRef.current && webSocketRef.current.readyState !== WebSocket.CLOSED) {
        webSocketRef.current.close();
        console.log("이전 WebSocket 연결 종료됨");
      }

      const ws = new WebSocket(WEBSOCKET_URL);
      ws.binaryType = 'arraybuffer'; // 바이너리 타입을 arraybuffer로 설정

      // 연결 성공 핸들러
      ws.onopen = () => {
        console.log('WebSocket 연결 성공');
        setStatusMessage('연결됨. 녹음 중...');
        setIsConnecting(false);
        webSocketRef.current = ws;
        resolve(ws);
      };

      // 메시지 수신 처리
      ws.onmessage = handleWebSocketMessage;

      // 오류 처리
      ws.onerror = (event: Event) => {
        console.error('WebSocket 오류:', event);
        setErrorMessage('WebSocket 연결 오류 발생');
        setIsConnecting(false);
        setIsRecording(false);
        setStatusMessage('연결 오류. 다시 시도하세요.');
        reject(new Error('WebSocket error occurred'));
      };

      // 연결 종료 처리
      ws.onclose = (event: CloseEvent) => {
        console.log('WebSocket 연결 종료:', event.code, event.reason);
        if (!event.wasClean) {
          setErrorMessage('WebSocket 연결이 예기치 않게 종료되었습니다.');
          setStatusMessage('연결 끊김. 다시 시도하세요.');
        }
        setIsRecording(false);
        setIsConnecting(false);
        webSocketRef.current = null;
        stopAudioStream();
      };
    });
  // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [stopAudioStream, processAudioQueue, stopRecording, enableResponseProcessing, handleInterruption]);

  // WebSocket 메시지 처리 함수
  const handleWebSocketMessage = useCallback((event: MessageEvent) => {
    // 서버에서 텍스트(JSON) 또는 바이너리 데이터를 보낼 수 있으므로 타입 확인
    if (typeof event.data === 'string') {
      console.log('WebSocket 텍스트 메시지 수신:', event.data);
      try {
        const data = parseWebSocketMessage(event.data);
        if (!data) return;

        // 감정 분석 결과 처리
        const emotion = processEmotionResult(data);
        if (emotion) {
          setCurrentEmotion(emotion);
        }

        // 인터럽션 처리
        if (isInterruptionSignal(data)) {
          handleInterruption();
          return;
        }

        // 응답 상태 메시지 처리
        const responseStatus = processResponseStatus(data);
        if (responseStatus.isStartProcessing) {
          // 응답 처리 시작 시간 기록
          responseStartTimeRef.current = Date.now();
          isFirstAudioChunkRef.current = true;
          
          // 상태 메시지 업데이트
          setResponseStatusMessage(responseStatus.message);
          setStatusMessage(responseStatus.message);
          
          // UI 상태 설정
          setIsResponseProcessing(true);
        } else if (responseStatus.isEndProcessing) {
          // 응답 처리 종료
          pendingResponseEnableRef.current = true;
          pendingResponseMessageRef.current = responseStatus.message;
          
          // 오디오 큐가 비어있는 경우에만 즉시 상태 업데이트
          if (audioQueueRef.current.length === 0 && !isPlayingRef.current) {
            enableResponseProcessing(pendingResponseMessageRef.current);
          } else {
            console.log(`아직 ${audioQueueRef.current.length}개의 오디오가 큐에 있고, 재생 중 상태: ${isPlayingRef.current}`);
          }
        }

        // 기타 텍스트 기반 메시지 처리
        if (data.transcript) {
          setTranscript(prev => prev + data.transcript);
          setStatusMessage('텍스트 수신 중...');
        }
        
        if (data.is_final) {
          setStatusMessage('최종 결과 수신.');
        }
        
        if (data.error) {
          console.error("WebSocket message error:", data.error);
          setErrorMessage(`서버 오류: ${data.error}`);
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
      console.warn("알 수 없는 메시지 타입 수신:", event.data);
    }
  }, [handleInterruption, processAudioQueue, stopRecording, enableResponseProcessing]);

  // MediaRecorder 설정 및 스트리밍 시작 함수
  const setupAndStartStreaming = useCallback(async (): Promise<boolean> => {
    if (!isSupported) {
      setErrorMessage('오디오 입력 또는 WebSocket을 지원하지 않는 브라우저입니다.');
      return false;
    }

    // 녹음용 AudioContext는 별도로 관리
    let recordingAudioContext: AudioContext | null = null;
    let recordingProcessor: ScriptProcessorNode | null = null;

    try {
      // 오디오 스트림 가져오기
      const stream: MediaStream = await navigator.mediaDevices.getUserMedia({
        audio: {
          channelCount: 1, 
          sampleRate: 16000,
          // 에코 제거 설정
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
        stopAudioStream();
        return false;
      }

      // Web Audio API를 사용하여 LINEAR16 PCM 데이터 생성
      recordingAudioContext = new (window.AudioContext || window.webkitAudioContext)({
        sampleRate: 16000 // 녹음은 16kHz
      });

      const source = recordingAudioContext.createMediaStreamSource(stream);
      recordingProcessor = recordingAudioContext.createScriptProcessor(4096, 1, 1);
      audioProcessorRef.current = recordingProcessor;

      // 오디오 처리 및 전송
      recordingProcessor.onaudioprocess = (e) => {
        if (webSocketRef.current?.readyState === WebSocket.OPEN) {
          const inputData = e.inputBuffer.getChannelData(0);
          const pcmData = convertFloat32ToPCM(inputData);
          webSocketRef.current.send(pcmData.buffer);
        }
      };

      // 오디오 노드 연결
      source.connect(recordingProcessor);
      recordingProcessor.connect(recordingAudioContext.destination);

      console.log('녹음 및 스트리밍 시작 (LINEAR16 PCM, 16kHz, 모노)');
      return true;

    } catch (err) {
      console.error('오디오 입력 접근 또는 오디오 처리 설정 오류:', err);
      if (err instanceof Error) {
        if (err.name === 'NotAllowedError' || err.name === 'PermissionDeniedError') {
          setErrorMessage('오디오 입력 사용 권한이 거부되었습니다.');
        } else {
          setErrorMessage(`오디오 입력 오류: ${err.message}`);
        }
      } else {
        setErrorMessage('알 수 없는 오디오 입력 접근 오류 발생');
      }
      setIsConnecting(false);

      // 오류 발생 시 녹음용 컨텍스트 정리
      if (recordingProcessor) recordingProcessor.disconnect();
      if (recordingAudioContext) recordingAudioContext.close();
      
      return false;
    }
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
      
      // 추가 정리 작업
      pendingResponseEnableRef.current = false;
      
      // 모든 활성 소스 노드 정리
      activeSourceNodes.current.forEach(node => {
        try {
          node.stop();
        } catch {
          // 이미 중지된 노드는 무시
        }
      });
      activeSourceNodes.current = [];
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
    stopRecording,
    isResponseProcessing,
    responseStatusMessage,
    processingTime,
    isPlayingAudio,
    lastAudioData,
    currentEmotion,
  };
}
