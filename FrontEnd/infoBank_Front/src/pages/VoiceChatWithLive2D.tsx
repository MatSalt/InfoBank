import React from 'react';
import { useVoiceStreaming } from '../hooks/useVoiceStreaming';
import Live2DAvatar from '../components/Live2DAvatar';
import { AudioProvider } from '../contexts/AudioContext';
import { EmotionType } from '../constants/emotions';

// 분리된 컴포넌트들 임포트
import { MicrophoneStatusIcon } from '../components/VoiceChat/MicrophoneStatusIcon';
import { SpeakerStatusIcon } from '../components/VoiceChat/SpeakerStatusIcon';
import { StatusMessage } from '../components/VoiceChat/StatusMessage';
import { EmotionDisplay } from '../components/VoiceChat/EmotionDisplay';
import { UnsupportedBrowserWarning } from '../components/VoiceChat/UnsupportedBrowserWarning';
import { ProcessingTime } from '../components/VoiceChat/ProcessingTime';
import { ControlButton } from '../components/VoiceChat/ControlButton';
import { TranscriptDisplay } from '../components/VoiceChat/TranscriptDisplay';
import { ErrorMessage } from '../components/VoiceChat/ErrorMessage';

/**
 * Live2D 아바타와 음성 채팅 기능을 제공하는 메인 페이지 컴포넌트
 */
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
    isResponseProcessing,
    responseStatusMessage,
    processingTime,
    lastAudioData,
    currentEmotion,
  } = useVoiceStreaming();

  return (
    <div className="flex flex-col md:flex-row w-full min-h-screen bg-gradient-to-br from-purple-100 to-blue-100">
      {/* Live2D 아바타 섹션 */}
      <div className="w-full md:w-1/2 h-[50vh] md:h-screen flex items-center justify-center p-4 relative">
        <div className="w-full h-full max-w-xl max-h-xl bg-white/50 rounded-xl shadow-lg overflow-hidden">
          <Live2DAvatar audioData={lastAudioData} emotion={currentEmotion as EmotionType} />
        </div>
      </div>

      {/* 음성 채팅 섹션 */}
      <div className="w-full md:w-1/2 p-4 flex flex-col items-center justify-center">
        <div className="w-full max-w-md p-6 bg-white rounded-xl shadow-lg">
          <h1 className="text-2xl font-bold mb-4 text-center text-gray-800">AI 음성 대화</h1>
          
          {/* 오디오 입력 상태 표시 */}
          <div className="flex justify-center space-x-8 mb-4">
            <MicrophoneStatusIcon isRecording={isRecording} />
            <SpeakerStatusIcon isProcessing={isResponseProcessing} />
          </div>
          
          {/* 상태 메시지 */}
          <StatusMessage 
            isRecording={isRecording}
            isResponseProcessing={isResponseProcessing}
            statusMessage={statusMessage}
            responseStatusMessage={responseStatusMessage}
          />
          
          {/* 현재 감정 상태 표시 */}
          <EmotionDisplay currentEmotion={currentEmotion} />
          
          {/* 지원 오류 메시지 */}
          <UnsupportedBrowserWarning isSupported={isSupported} />
          
          {/* 처리 시간 표시 */}
          <ProcessingTime processingTime={processingTime} />
          
          {/* 시작/중지 버튼 */}
          <ControlButton 
            isRecording={isRecording}
            isConnecting={isConnecting}
            isSupported={isSupported}
            onStartRecording={startRecording}
            onStopRecording={stopRecording}
          />
          
          {/* 인식된 텍스트 */}
          <TranscriptDisplay transcript={transcript} />
          
          {/* 오류 메시지 */}
          <ErrorMessage errorMessage={errorMessage} />
        </div>
      </div>
    </div>
  );
};

/**
 * AudioProvider로 감싸서 내보내는 최상위 컴포넌트
 */
const VoiceChatWithLive2DPage: React.FC = () => (
  <AudioProvider>
    <VoiceChatWithLive2D />
  </AudioProvider>
);

export default VoiceChatWithLive2DPage; 