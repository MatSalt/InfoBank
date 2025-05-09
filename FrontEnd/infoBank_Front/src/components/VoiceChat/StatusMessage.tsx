import React from 'react';

/**
 * 현재 시스템 상태를 텍스트로 표시하는 컴포넌트
 */
interface StatusMessageProps {
  isRecording: boolean;
  isResponseProcessing: boolean;
  statusMessage: string;
  responseStatusMessage: string;
}

export const StatusMessage: React.FC<StatusMessageProps> = ({
  isRecording,
  isResponseProcessing,
  statusMessage,
  responseStatusMessage
}) => {
  const messageText = isResponseProcessing ? '🔊 ' + responseStatusMessage : statusMessage;
  
  return (
    <p className={`text-center font-medium mb-4 ${
      isResponseProcessing ? 'text-red-600' : 
      isRecording ? 'text-green-600' : 
      'text-gray-600'
    }`}>
      {messageText}
    </p>
  );
}; 