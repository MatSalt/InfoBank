import React from 'react';

/**
 * AI 응답 처리 시간을 표시하는 컴포넌트
 */
interface ProcessingTimeProps {
  processingTime: number | null;
}

export const ProcessingTime: React.FC<ProcessingTimeProps> = ({ processingTime }) => {
  if (processingTime === null) return null;
  
  return (
    <div className="mb-4 p-2 bg-yellow-50 border border-yellow-200 rounded-lg text-center">
      <p className="text-yellow-700 text-sm">
        ⏱️ 응답 처리 시간: {processingTime.toFixed(2)}초
      </p>
    </div>
  );
}; 