import React, { createContext, useContext, useState, useRef, useCallback, useEffect } from 'react';
import { createLogger } from '../utils/logger';

// 로거 인스턴스 생성
const logger = createLogger('AudioContext');

// 컨텍스트 인터페이스 정의
interface AudioContextType {
  // audioData: Uint8Array | null; // 더 이상 직접 전달 안 함
  isAudioPlaying: boolean;
  analyserNode: AnalyserNode | null; // AnalyserNode 추가
  audioContext: AudioContext | null; // AudioContext 인스턴스 추가
  isInitialized: boolean; // 초기화 상태 추가
  processingAudio: () => void; // 데이터를 받지 않고 상태만 변경
  clearAudio: () => void;
}

// 기본값으로 컨텍스트 생성
const AudioContext = createContext<AudioContextType>({
  // audioData: null,
  isAudioPlaying: false,
  analyserNode: null,
  audioContext: null, // 기본값 null
  isInitialized: false, // 기본값 false
  processingAudio: () => {},
  clearAudio: () => {},
});

// 커스텀 훅 생성
export const useAudio = () => useContext(AudioContext);

// 프로바이더 컴포넌트
export const AudioProvider: React.FC<{ children: React.ReactNode }> = ({ children }) => {
  // const [audioData, setAudioData] = useState<Uint8Array | null>(null);
  const [isAudioPlaying, setIsAudioPlaying] = useState<boolean>(false);
  const [isInitialized, setIsInitialized] = useState<boolean>(false); // State 추가
  const audioContextRef = useRef<AudioContext | null>(null);
  const analyserNodeRef = useRef<AnalyserNode | null>(null);

  // AudioContext 및 AnalyserNode 초기화
  useEffect(() => {
    // 이미 초기화되었으면 다시 실행 안 함 (선택 사항)
    if (audioContextRef.current) return;

    let localAudioContext: AudioContext | null = null; // 지역 변수로 생성
    let localAnalyserNode: AnalyserNode | null = null;

    try {
      const AudioContextClass = window.AudioContext || window.webkitAudioContext;
      if (!AudioContextClass) {
        logger.error('AudioContext is not supported in this browser.');
        return;
      }
      // --- 중요: TTS 샘플링 레이트(24000Hz)에 맞춰 AudioContext 생성 ---
      localAudioContext = new AudioContextClass({ sampleRate: 24000 });
      // --------------------------------------------------------------
      localAnalyserNode = localAudioContext.createAnalyser();
      localAnalyserNode.fftSize = 256; // 예시 fftSize, 필요시 조정
      // smoothingTimeConstant 설정은 AnalyserNode 자체보다는 데이터 처리 로직에서 하는 것이 더 유연할 수 있음
      // localAnalyserNode.smoothingTimeConstant = 0.1; // 필요시 설정

      // *** AnalyserNode를 destination에 미리 연결 ***
      // AnalyserNode는 데이터를 분석만 하고 통과시키므로, 미리 연결해두면
      // source -> analyser -> destination 경로가 완성됨.
      if (localAudioContext && localAnalyserNode) {
          localAnalyserNode.connect(localAudioContext.destination);
          logger.debug('AnalyserNode connected to destination.');
      }
      // *******************************************

      // Ref 업데이트
      audioContextRef.current = localAudioContext;
      analyserNodeRef.current = localAnalyserNode;

      // *** 초기화 완료 상태 업데이트 ***
      setIsInitialized(true);
      // ***************************

      logger.info(`AudioContext (Sample Rate: ${localAudioContext.sampleRate}Hz) and AnalyserNode initialized.`);
    } catch (error) {
      logger.error('Error initializing AudioContext:', error);
    }

    // Cleanup 함수
    return () => {
      if (localAudioContext && localAudioContext.state !== 'closed') {
        localAudioContext.close().catch(err => logger.error('Error closing AudioContext:', err));
        // Ref 초기화는 Provider 언마운트 시 자동 처리되므로 여기서 반드시 null로 설정할 필요는 없음
        // audioContextRef.current = null;
        // analyserNodeRef.current = null;
        setIsInitialized(false); // 언마운트 시 초기화 상태 false로
        logger.debug('AudioContext closed.');
      }
    };
  }, []); // 빈 배열 유지 (마운트 시 한 번 실행)

  // 오디오 처리 시작 알림 함수
  const processingAudio = useCallback(() => {
    logger.debug('processingAudio called - Setting isAudioPlaying true');
    // AnalyserNode가 활성화되도록 resume() 호출 (필요한 경우)
    if (audioContextRef.current?.state === 'suspended') {
        audioContextRef.current.resume();
    }
    setIsAudioPlaying(true);
  }, []);

  // 오디오 데이터 정리 함수
  const clearAudio = useCallback(() => {
    logger.debug('clearAudio called - Setting isAudioPlaying false');
    setIsAudioPlaying(false);
    // setAudioData(null); // 더 이상 사용 안 함
  }, []);

  // 컨텍스트 값 (isInitialized 포함)
  const value = {
    // audioData, // 제거
    isAudioPlaying,
    analyserNode: analyserNodeRef.current, // ref의 현재 값을 전달
    audioContext: audioContextRef.current, // audioContext 인스턴스 전달
    isInitialized, // 상태 전달
    processingAudio,
    clearAudio,
  };

  // --- 로그 레벨 조정 ---
  logger.debug('Providing context value:', {
      isAudioPlaying,
      analyserNode: !!analyserNodeRef.current, // 실제 노드 대신 존재 여부만 로깅
      audioContext: !!audioContextRef.current, // 실제 컨텍스트 대신 존재 여부만 로깅
      isInitialized, // 상태 로깅
  });
  // -----------------

  return (
    <AudioContext.Provider value={value}>
      {children}
    </AudioContext.Provider>
  );
}; 