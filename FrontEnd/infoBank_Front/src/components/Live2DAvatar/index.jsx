import React, { useState, useEffect } from 'react';
import Live2DCanvas from './Live2DCanvas';

const Live2DAvatar = ({ audioSource }) => {
  // 오디오 소스를 받아서 립싱크 처리 로직 추가 예정
  const modelPath = '/assets/live2d/Haru/Haru.model3.json';

  return (
    <div style={{ width: '400px', height: '400px' }}>
      <Live2DCanvas modelPath={modelPath} />
    </div>
  );
};

export default Live2DAvatar;