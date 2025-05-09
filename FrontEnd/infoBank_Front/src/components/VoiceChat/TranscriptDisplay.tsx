import React from 'react';

/**
 * 음성 인식 결과 텍스트를 표시하는 컴포넌트
 */
interface TranscriptDisplayProps {
  transcript: string | null;
}

export const TranscriptDisplay: React.FC<TranscriptDisplayProps> = ({ transcript }) => {
  if (!transcript) return null;
  
  return (
    <div className="mt-6 p-4 bg-gray-50 rounded-lg">
      <h2 className="text-lg font-semibold mb-2 text-gray-700">인식된 텍스트:</h2>
      <p className="text-gray-600 whitespace-pre-wrap">{transcript}</p>
    </div>
  );
}; 