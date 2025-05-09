import React from 'react';

/**
 * 음성 녹음 시작/중지를 제어하는 버튼 컴포넌트
 */
interface ControlButtonProps {
  isRecording: boolean;
  isConnecting: boolean;
  isSupported: boolean;
  onStartRecording: () => void;
  onStopRecording: () => void;
}

export const ControlButton: React.FC<ControlButtonProps> = ({
  isRecording,
  isConnecting,
  isSupported,
  onStartRecording,
  onStopRecording
}) => {
  const handleClick = () => {
    if (isRecording) {
      onStopRecording();
    } else {
      onStartRecording();
    }
  };

  const buttonText = isRecording 
    ? '🔴 대화 중지' 
    : (isConnecting ? '연결 중...' : '🎤 대화 시작');

  return (
    <button
      onClick={handleClick}
      disabled={!isSupported || isConnecting}
      className={`w-full px-6 py-4 rounded-lg text-white font-semibold shadow-md transition-all duration-300 ease-in-out ${
        isRecording
          ? 'bg-red-500 hover:bg-red-600 animate-pulse' 
          : 'bg-purple-600 hover:bg-purple-700'
      } ${(!isSupported || isConnecting) ? 'opacity-50 cursor-not-allowed' : ''}`}
    >
      {buttonText}
    </button>
  );
}; 