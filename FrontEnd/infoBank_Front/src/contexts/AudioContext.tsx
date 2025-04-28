import React, { createContext, useContext, useState, useRef, useCallback } from 'react';

// 컨텍스트 인터페이스 정의
interface AudioContextType {
  audioData: Uint8Array | null;
  isAudioPlaying: boolean;
  processingAudio: (data: Uint8Array) => void;
  clearAudio: () => void;
}

// 기본값으로 컨텍스트 생성
const AudioContext = createContext<AudioContextType>({
  audioData: null,
  isAudioPlaying: false,
  processingAudio: () => {},
  clearAudio: () => {},
});

// 커스텀 훅 생성
export const useAudio = () => useContext(AudioContext);

// 프로바이더 컴포넌트
export const AudioProvider: React.FC<{ children: React.ReactNode }> = ({ children }) => {
  const [audioData, setAudioData] = useState<Uint8Array | null>(null);
  const [isAudioPlaying, setIsAudioPlaying] = useState<boolean>(false);
  
  // 현재 처리 중인 오디오 데이터 추적을 위한 ref
  const currentProcessingRef = useRef<ReturnType<typeof setTimeout> | null>(null);
  
  // 오디오 데이터 처리 함수
  const processingAudio = useCallback((data: Uint8Array) => {
	console.log('AudioContext에 데이터 도착:', {
		byteLength: data?.byteLength,
		isValidArray: data instanceof Uint8Array,
		isEmpty: data?.length === 0
	  });
    setAudioData(data);
    setIsAudioPlaying(true);
    
    // // 이전 타이머가 있으면 제거 (오디오 데이터 정리 타이머 제거)
    // if (currentProcessingRef.current) {
    //   clearTimeout(currentProcessingRef.current);
    // }
    
    // // 오디오 데이터는 clearAudio 호출 시 정리됨
    // currentProcessingRef.current = setTimeout(() => {
    //     setAudioData(null);
    // }, 500); 

  }, []);
  
  // 오디오 데이터 정리 함수
  const clearAudio = useCallback(() => {
    // // 더 이상 currentProcessingRef를 사용하지 않으므로 관련 로직 제거
    // if (currentProcessingRef.current) {
    //   clearTimeout(currentProcessingRef.current);
    //   currentProcessingRef.current = null;
    // }
    console.log('[AudioContext] clearAudio 호출됨'); // clearAudio 호출 로그 추가
    setIsAudioPlaying(false);
    setAudioData(null);
  }, []);
  
  // 컨텍스트 값
  const value = {
    audioData,
    isAudioPlaying,
    processingAudio,
    clearAudio,
  };
  
  return (
    <AudioContext.Provider value={value}>
      {children}
    </AudioContext.Provider>
  );
}; 