// 커스텀 훅 임포트 (useVoiceStreaming.ts 파일로부터)
import { useVoiceStreaming } from '../hooks/useVoiceStreaming';

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
    isMicDisabled,    // 추가된 상태
    micStatusMessage,  // 추가된 상태
    isPlayingAudio,    // 추가: 현재 오디오 재생 중인지 상태
  } = useVoiceStreaming();

  // JSX 반환 (타입: JSX.Element)
  return (
    <div className="flex flex-col items-center justify-center w-full h-full min-h-screen bg-gradient-to-b from-purple-100 to-purple-300 font-sans p-4">
      <div className="w-full max-w-md p-6 bg-white rounded-xl shadow-lg text-center">
        <h1 className="text-2xl font-bold mb-4 text-gray-800">AI 음성 대화</h1>

        {/* 마이크 상태 표시 - 시각적 피드백 추가 */}
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
        
        {/* 마이크 상태 메시지 */}
        <p className={`text-sm font-medium mb-4 ${isMicDisabled ? 'text-red-500' : 'text-gray-600'}`}>
          {isMicDisabled ? micStatusMessage : (isRecording ? '녹음 중...' : '대기 중')}
        </p>

        {/* 브라우저 지원 여부 메시지 */}
        {!isSupported && (
          <p className="text-red-600 bg-red-100 p-3 rounded-lg mb-4">
            ⚠️ 현재 사용 중인 브라우저에서는 마이크 녹음 또는 WebSocket을 지원하지 않습니다. 최신 Chrome, Firefox, Edge 브라우저를 사용해 주세요.
          </p>
        )}

        {/* 상태 메시지 표시 */}
        <p className={`text-lg text-gray-600 mb-6 h-6 ${isConnecting ? 'animate-pulse' : ''}`}>{statusMessage}</p>

        {/* 오디오 및 마이크 상태 표시 - 확장 */}
        <div className={`mt-4 p-3 ${isMicDisabled ? 'bg-red-50 border border-red-200' : 'bg-blue-50'} rounded-lg flex items-center gap-2`}>
          {isMicDisabled && (
            <div className="flex-shrink-0 w-4 h-4 rounded-full bg-red-500 animate-pulse"></div>
          )}
          <p className={`${isMicDisabled ? 'text-red-600' : 'text-blue-600'}`}>
            {isMicDisabled 
              ? `🔇 마이크 비활성화됨: ${micStatusMessage || 'AI가 응답 중입니다...'}`
              : '🎤 마이크가 활성화되었습니다. 말씀하세요.'}
          </p>
        </div>
        
        {/* 오디오 재생 상태 표시 */}
        {isPlayingAudio && (
          <div className="mt-2 p-3 bg-green-50 border border-green-200 rounded-lg flex items-center gap-2">
            <div className="flex-shrink-0 w-4 h-4 rounded-full bg-green-500 animate-pulse"></div>
            <p className="text-green-600">
              🔊 AI 음성 응답 재생 중...
            </p>
          </div>
        )}

        {/* 시작/중지 버튼 */}
        <button
          onClick={isRecording ? stopRecording : startRecording}
          disabled={!isSupported || isConnecting || isMicDisabled} // 마이크 비활성화 시 버튼도 비활성화
          className={`w-full px-6 py-4 rounded-lg text-white font-semibold shadow-md transition-all duration-300 ease-in-out ${
            isRecording
              ? 'bg-red-500 hover:bg-red-600 animate-pulse' 
              : 'bg-purple-600 hover:bg-purple-700'
          } ${(!isSupported || isConnecting || isMicDisabled) ? 'opacity-50 cursor-not-allowed' : ''}`}
        >
          {isRecording ? '🔴 녹음 중지' : (isConnecting ? '연결 중...' : (isMicDisabled ? '처리 중...' : '🎤 대화 시작'))}
        </button>

        {/* 인식된 텍스트 표시 영역 */}
        {transcript && (
          <div className="mt-6 p-4 bg-gray-50 rounded-lg text-left">
            <h2 className="text-lg font-semibold mb-2 text-gray-700">인식된 텍스트:</h2>
            <p className="text-gray-600 whitespace-pre-wrap">{transcript}</p>
          </div>
        )}

        {/* TTS 오디오 재생 상태 표시 */}
        <div className="mt-4 p-3 bg-blue-50 rounded-lg">
          <p className="text-blue-600">
            🔊 TTS 오디오 재생: 서버에서 받은 음성 응답이 자동으로 재생됩니다.
          </p>
        </div>

        {/* 오류 메시지 표시 */}
        {errorMessage && (
          <div className="mt-4 p-3 bg-red-100 text-red-600 rounded-lg">
            <p>⚠️ {errorMessage}</p>
          </div>
        )}
      </div>
    </div>
  );
}

// export default VoiceChatPage; // 함수 선언 시 export default 사용 가능
