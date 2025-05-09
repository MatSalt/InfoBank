import React from 'react';
import { useVoiceStreaming } from '../hooks/useVoiceStreaming';
import Live2DAvatar from '../components/Live2DAvatar';
import { AudioProvider } from '../contexts/AudioContext';

// 감정 이모지 매핑
const EMOTION_EMOJI = {
  "기쁨": "😊",
  "화남": "😠",
  "짜증": "😒",
  "속상함": "😢",
  "슬픔": "😥",
  "행복": "😄",
  "놀라움": "😲",
  "부끄러움": "😳",
  "싫증": "😑",
  "귀찮음": "😩",
  "중립": "😐"
};

const VoiceChatWithLive2D: React.FC = () => {
  // 커스텀 훅 사용
  const {
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
    lastAudioData,
    currentEmotion, // 감정 상태 추가
  } = useVoiceStreaming();

  // 현재 감정에 해당하는 이모지 가져오기
  const emotionEmoji = EMOTION_EMOJI[currentEmotion] || EMOTION_EMOJI["중립"];

  return (
    <div className="flex flex-col md:flex-row w-full min-h-screen bg-gradient-to-br from-purple-100 to-blue-100">
      {/* Live2D 아바타 섹션 */}
      <div className="w-full md:w-1/2 h-[50vh] md:h-screen flex items-center justify-center p-4 relative">
        <div className="w-full h-full max-w-xl max-h-xl bg-white/50 rounded-xl shadow-lg overflow-hidden">
          <Live2DAvatar audioData={lastAudioData} emotion={currentEmotion} />
          
          {/* 상태 오버레이 */}
          {isMicDisabled && (
            <div className="absolute top-4 right-4 bg-red-500 text-white px-3 py-1 rounded-full text-sm animate-pulse">
              AI 응답 중...
            </div>
          )}
        </div>
      </div>

      {/* 음성 채팅 섹션 */}
      <div className="w-full md:w-1/2 p-4 flex flex-col items-center justify-center">
        <div className="w-full max-w-md p-6 bg-white rounded-xl shadow-lg">
          <h1 className="text-2xl font-bold mb-4 text-center text-gray-800">AI 음성 대화</h1>
          
          {/* 마이크 상태 표시 */}
          <div className={`relative mx-auto w-20 h-20 rounded-full flex items-center justify-center mb-4 transition-all duration-300
            ${isMicDisabled 
              ? 'bg-red-100 border-2 border-red-400' 
              : isRecording 
                ? 'bg-green-100 border-2 border-green-500 animate-pulse' 
                : 'bg-gray-100 border-2 border-gray-300'}`}>
            
            {/* 마이크 아이콘 */}
            <svg 
              className={`w-10 h-10 transition-all duration-300 ${isMicDisabled ? 'text-red-500' : isRecording ? 'text-green-600' : 'text-gray-500'}`} 
              fill="none" 
              stroke="currentColor" 
              viewBox="0 0 24 24" 
              xmlns="http://www.w3.org/2000/svg">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M19 11a7 7 0 01-7 7m0 0a7 7 0 01-7-7m7 7v4m0 0H8m4 0h4m-4-8a3 3 0 01-3-3V5a3 3 0 116 0v6a3 3 0 01-3 3z" />
            </svg>
            
            {/* 마이크 비활성화 시 X 표시 */}
            {isMicDisabled && (
              <div className="absolute inset-0 flex items-center justify-center">
                <svg className="w-16 h-16 text-red-500 opacity-70" fill="none" stroke="currentColor" viewBox="0 0 24 24" xmlns="http://www.w3.org/2000/svg">
                  <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={3} d="M6 18L18 6M6 6l12 12" />
                </svg>
              </div>
            )}
          </div>
          
          {/* 상태 메시지 */}
          <p className={`text-center font-medium mb-4 ${isMicDisabled ? 'text-red-600' : isRecording ? 'text-green-600' : 'text-gray-600'}`}>
            {isMicDisabled ? micStatusMessage : statusMessage}
          </p>
          
          {/* 현재 감정 상태 표시 */}
          <div className="mb-4 p-3 bg-blue-50 rounded-lg text-center">
            <p className="text-blue-700 text-sm font-medium">
              감정 상태: {emotionEmoji} {currentEmotion}
            </p>
          </div>
          
          {/* 지원 오류 메시지 */}
          {!isSupported && (
            <div className="mb-4 p-3 bg-red-100 rounded-lg text-red-600 text-sm">
              ⚠️ 현재 브라우저에서는 마이크 녹음 또는 WebSocket을 지원하지 않습니다. 최신 Chrome, Firefox, Edge 브라우저를 사용해 주세요.
            </div>
          )}
          
          {/* 처리 시간 표시 */}
          {processingTime !== null && (
            <div className="mb-4 p-2 bg-yellow-50 border border-yellow-200 rounded-lg text-center">
              <p className="text-yellow-700 text-sm">
                ⏱️ 응답 처리 시간: {processingTime.toFixed(2)}초
              </p>
            </div>
          )}
          
          {/* 시작/중지 버튼 */}
          <button
            onClick={isRecording ? stopRecording : startRecording}
            disabled={!isSupported || isConnecting || isMicDisabled}
            className={`w-full px-6 py-4 rounded-lg text-white font-semibold shadow-md transition-all duration-300 ease-in-out ${
              isRecording
                ? 'bg-red-500 hover:bg-red-600 animate-pulse' 
                : 'bg-purple-600 hover:bg-purple-700'
            } ${(!isSupported || isConnecting || isMicDisabled) ? 'opacity-50 cursor-not-allowed' : ''}`}
          >
            {isRecording ? '🔴 녹음 중지' : (isConnecting ? '연결 중...' : (isMicDisabled ? '처리 중...' : '🎤 대화 시작'))}
          </button>
          
          {/* 인식된 텍스트 */}
          {transcript && (
            <div className="mt-6 p-4 bg-gray-50 rounded-lg">
              <h2 className="text-lg font-semibold mb-2 text-gray-700">인식된 텍스트:</h2>
              <p className="text-gray-600 whitespace-pre-wrap">{transcript}</p>
            </div>
          )}
          
          {/* 오류 메시지 */}
          {errorMessage && (
            <div className="mt-4 p-3 bg-red-100 text-red-600 rounded-lg text-sm">
              <p>⚠️ {errorMessage}</p>
            </div>
          )}
        </div>
      </div>
    </div>
  );
};

// AudioProvider로 감싸서 내보내기
const VoiceChatWithLive2DPage: React.FC = () => (
  <AudioProvider>
    <VoiceChatWithLive2D />
  </AudioProvider>
);

export default VoiceChatWithLive2DPage; 