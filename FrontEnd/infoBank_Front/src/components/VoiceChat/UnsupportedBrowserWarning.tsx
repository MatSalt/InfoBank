import React from 'react';

/**
 * 브라우저 호환성 경고를 표시하는 컴포넌트
 */
interface UnsupportedBrowserWarningProps {
  isSupported: boolean;
}

export const UnsupportedBrowserWarning: React.FC<UnsupportedBrowserWarningProps> = ({ isSupported }) => {
  if (isSupported) return null;
  
  return (
    <div className="mb-4 p-3 bg-red-100 rounded-lg text-red-600 text-sm">
      ⚠️ 현재 브라우저에서는 오디오 입력 또는 WebSocket을 지원하지 않습니다. 최신 Chrome, Firefox, Edge 브라우저를 사용해 주세요.
    </div>
  );
}; 