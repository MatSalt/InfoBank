import React from 'react';

/**
 * AI 응답 상태를 시각적으로 표시하는 컴포넌트
 * 응답 처리 중일 때만 표시됩니다.
 */
interface SpeakerStatusIconProps {
  isProcessing: boolean;
}

export const SpeakerStatusIcon: React.FC<SpeakerStatusIconProps> = ({ isProcessing }) => {
  if (!isProcessing) return null;
  
  return (
    <div className="relative w-20 h-20 rounded-full flex items-center justify-center bg-red-100 border-2 border-red-400 animate-pulse">
      <svg 
        className="w-10 h-10 text-red-500" 
        fill="none" 
        stroke="currentColor" 
        viewBox="0 0 24 24" 
        xmlns="http://www.w3.org/2000/svg">
        <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M15.536 8.464a5 5 0 010 7.072m2.828-9.9a9 9 0 010 12.728M5.586 15.536a5 5 0 001.414 1.414m2.828-4.242a1 1 0 011.414 0 1 1 0 010 1.414m0 0l-2.828 2.828m0 0a3 3 0 01-4.243 0 3 3 0 010-4.243" />
      </svg>
    </div>
  );
}; 