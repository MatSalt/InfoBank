import React from 'react';

/**
 * 마이크 상태를 시각적으로 표시하는 컴포넌트
 * 녹음 상태에 따라 색상과 애니메이션이 변경됩니다.
 */
interface MicrophoneStatusIconProps {
  isRecording: boolean;
}

export const MicrophoneStatusIcon: React.FC<MicrophoneStatusIconProps> = ({ isRecording }) => (
  <div className={`relative w-20 h-20 rounded-full flex items-center justify-center transition-all duration-300
    ${isRecording 
      ? 'bg-green-100 border-2 border-green-500 animate-pulse' 
      : 'bg-blue-50 border-2 border-blue-300'}`}>
    
    <svg 
      className={`w-10 h-10 transition-all duration-300 ${isRecording ? 'text-green-600' : 'text-blue-500'}`} 
      fill="none" 
      stroke="currentColor" 
      viewBox="0 0 24 24" 
      xmlns="http://www.w3.org/2000/svg">
      <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M19 11a7 7 0 01-7 7m0 0a7 7 0 01-7-7m7 7v4m0 0H8m4 0h4m-4-8a3 3 0 01-3-3V5a3 3 0 116 0v6a3 3 0 01-3 3z" />
    </svg>
  </div>
); 