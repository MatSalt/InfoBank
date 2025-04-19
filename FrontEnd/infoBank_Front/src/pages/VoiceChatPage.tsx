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
  } = useVoiceStreaming();

  // JSX 반환 (타입: JSX.Element)
  return (
    <div className="flex flex-col items-center justify-center w-full h-full min-h-screen bg-gradient-to-b from-purple-100 to-purple-300 font-sans p-4">
      <div className="w-full max-w-md p-6 bg-white rounded-xl shadow-lg text-center">
        <h1 className="text-2xl font-bold mb-4 text-gray-800">AI 음성 대화</h1>

        {/* 브라우저 지원 여부 메시지 */}
        {!isSupported && (
          <p className="text-red-600 bg-red-100 p-3 rounded-lg mb-4">
            ⚠️ 현재 사용 중인 브라우저에서는 마이크 녹음 또는 WebSocket을 지원하지 않습니다. 최신 Chrome, Firefox, Edge 브라우저를 사용해 주세요.
          </p>
        )}

        {/* 상태 메시지 표시 */}
        <p className={`text-lg text-gray-600 mb-6 h-6 ${isConnecting ? 'animate-pulse' : ''}`}>{statusMessage}</p>

        {/* 시작/중지 버튼 */}
        <button
          onClick={isRecording ? stopRecording : startRecording}
          disabled={!isSupported || isConnecting} // 미지원 또는 연결 중일 때 비활성화
          className={`w-full px-6 py-4 rounded-lg text-white font-semibold shadow-md transition-all duration-300 ease-in-out ${
            isRecording
              ? 'bg-red-500 hover:bg-red-600 animate-pulse' // 녹음 중일 때 빨간색 및 애니메이션
              : 'bg-purple-600 hover:bg-purple-700' // 기본 상태 보라색
          } ${(!isSupported || isConnecting) ? 'opacity-50 cursor-not-allowed' : ''}`} // 비활성화 스타일
        >
          {isRecording ? '🔴 녹음 중지' : (isConnecting ? '연결 중...' : '🎤 대화 시작')}
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
