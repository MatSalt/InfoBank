// 커스텀 훅 임포트 (useVoiceStreaming.ts 파일로부터)
import React from 'react';
import { useVoiceStreaming } from '../hooks/useVoiceStreaming';
import { AudioProvider } from '../contexts/AudioContext';

// React Functional Component 타입 사용 (선택 사항, 함수 선언으로도 타입 추론 가능)
// const VoiceChatPage: React.FC = () => {
export default function VoiceChatPage() { // 간단한 함수 선언 방식 사용
  // 커스텀 훅 사용 - 반환 값의 타입은 useVoiceStreaming 훅에 정의된 UseVoiceStreamingReturn 인터페이스로 추론됨
  const {
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
    currentEmotion
  } = useVoiceStreaming();

  // JSX 반환 (타입: JSX.Element)
  return (
    <div className="container mx-auto p-4 max-w-4xl">
      <h1 className="text-2xl font-bold mb-6 text-center">음성 채팅 데모</h1>
      
      <div className="bg-white p-6 rounded-lg shadow-md mb-6">
        {/* 오디오 입력 상태 표시 - 시각적 피드백 추가 */}
        <div className="flex justify-center mb-6">
          <div className={`relative w-20 h-20 flex items-center justify-center rounded-full 
            ${isRecording ? 'bg-green-100' : 'bg-gray-100'} 
            ${isRecording ? 'border-4 border-green-500 animate-pulse' : 'border-2 border-gray-300'}`}>
            
            {/* 오디오 아이콘 */}
            <svg 
              className={`w-10 h-10 ${isRecording ? 'text-green-600' : 'text-gray-500'}`} 
              fill="none" 
              stroke="currentColor" 
              viewBox="0 0 24 24" 
              xmlns="http://www.w3.org/2000/svg">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M19 11a7 7 0 01-7 7m0 0a7 7 0 01-7-7m7 7v4m0 0H8m4 0h4m-4-8a3 3 0 01-3-3V5a3 3 0 116 0v6a3 3 0 01-3 3z" />
            </svg>
            
            {/* 응답 처리 중일 때 X 표시 */}
            {isResponseProcessing && (
              <div className="absolute inset-0 flex items-center justify-center">
                <svg className="w-16 h-16 text-red-500 opacity-70" fill="none" stroke="currentColor" viewBox="0 0 24 24" xmlns="http://www.w3.org/2000/svg">
                  <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={3} d="M6 18L18 6M6 6l12 12" />
                </svg>
              </div>
            )}
          </div>
        </div>
        
        {/* 오디오 입력 상태 메시지 */}
        <p className="text-center text-lg font-medium mb-4">
          {statusMessage}
        </p>
        
        {/* 지원 오류 */}
        {!isSupported && (
          <div className="bg-red-100 p-4 rounded-md text-red-700 mb-4">
            ⚠️ 현재 사용 중인 브라우저에서는 오디오 입력 또는 WebSocket을 지원하지 않습니다. 최신 Chrome, Firefox, Edge 브라우저를 사용해 주세요.
          </div>
        )}
        
        {/* 오디오 및 응답 상태 표시 - 확장 */}
        <div className="mb-6">
          <div className={`text-center mb-2 py-2 px-3 rounded-md ${
            isResponseProcessing 
              ? 'bg-red-100 text-red-800'
              : isRecording 
                ? 'bg-green-100 text-green-800' 
                : 'bg-gray-100 text-gray-700'}`}>
            {isResponseProcessing 
            ? `🔇 응답 처리 중: ${responseStatusMessage || 'AI가 응답 중입니다...'}`
            : '🎤 오디오 입력 활성화되었습니다. 말씀하세요.'}
          </div>
          
          {/* 현재 감정 표시 */}
          {currentEmotion && (
            <div className="text-center py-2 px-3 bg-blue-50 text-blue-700 rounded-md mb-2">
              감정 상태: {currentEmotion}
            </div>
          )}
          
          {/* 처리 시간 표시 */}
          {processingTime !== null && (
            <div className="text-center py-2 px-3 bg-yellow-50 text-yellow-700 rounded-md">
              ⏱️ 응답 처리 시간: {processingTime.toFixed(2)}초
            </div>
          )}
        </div>
        
        {/* 시작/중지 버튼 */}
        <div className="flex justify-center mb-6">
          <button
            onClick={isRecording ? stopRecording : startRecording}
            disabled={!isSupported || isConnecting || isResponseProcessing} // 응답 처리 중일 때 버튼도 비활성화
            className={`py-3 px-6 rounded-lg font-bold text-white ${
              isRecording 
                ? 'bg-red-500 hover:bg-red-600' 
                : 'bg-blue-500 hover:bg-blue-600'
            } ${
              (!isSupported || isConnecting || isResponseProcessing) ? 'opacity-50 cursor-not-allowed' : ''
            }`}
          >
            {isRecording ? '🛑 녹음 중지' : (isConnecting ? '연결 중...' : '🎤 녹음 시작')}
          </button>
        </div>
        
        {/* 트랜스크립트 표시 (추가) */}
        {transcript && (
          <div className="mt-6">
            <h3 className="font-semibold mb-2">인식된 텍스트:</h3>
            <div className="bg-gray-50 p-4 rounded-md whitespace-pre-wrap">
              {transcript}
            </div>
          </div>
        )}
        
        {/* 오류 메시지 */}
        {errorMessage && (
          <div className="mt-4 bg-red-100 p-4 rounded-md text-red-700">
            <p>⚠️ {errorMessage}</p>
          </div>
        )}
      </div>
    </div>
  );
}

// export default VoiceChatPage; // 함수 선언 시 export default 사용 가능

// AudioProvider로 감싸서 내보내기
const VoiceChatWithAudioProvider: React.FC = () => (
  <AudioProvider>
    <VoiceChatPage />
  </AudioProvider>
);

export default VoiceChatWithAudioProvider;
