import React from 'react';

/**
 * 오류 메시지를 표시하는 컴포넌트
 */
interface ErrorMessageProps {
  errorMessage: string | null;
}

export const ErrorMessage: React.FC<ErrorMessageProps> = ({ errorMessage }) => {
  if (!errorMessage) return null;
  
  return (
    <div className="mt-4 p-3 bg-red-100 text-red-600 rounded-lg text-sm">
      <p>⚠️ {errorMessage}</p>
    </div>
  );
}; 