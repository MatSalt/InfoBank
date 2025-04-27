import React from 'react';
import Live2DCanvas from './Live2DCanvas';

const Live2DAvatar = ({ audioSource }) => {
  // 모델 경로 수정
  const modelPath = '/assets/live2d/Haru/Haru.model3.json';

  return (
    <div style={{ 
      width: '100%', 
      height: '100vh', 
      maxHeight: '800px',
      display: 'flex', 
      justifyContent: 'center', 
      alignItems: 'center'
    }}>
      <div style={{ 
        width: '100%', 
        height: '100%', 
        maxWidth: '600px',
        position: 'relative'
      }}>
        <Live2DCanvas modelPath={modelPath} />
      </div>
    </div>
  );
};

export default Live2DAvatar;