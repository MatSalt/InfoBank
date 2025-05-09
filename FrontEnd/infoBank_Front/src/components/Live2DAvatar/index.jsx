import React from 'react';
import Live2DCanvas from './Live2DCanvas';

const Live2DAvatar = ({ audioData, emotion = "중립", backgroundImage }) => {
  // 모델 경로 설정
  const modelPath = '/assets/live2d/Haru/Haru.model3.json';
  
  // 기본 배경 이미지 설정
  const defaultBackgroundImage = '/assets/images/backgrounds/42seoul.jpeg';
  
  return (
    <div style={{ 
      width: '100%', 
      height: '100%',
      display: 'flex', 
      justifyContent: 'center', 
      alignItems: 'center'
    }}>
      <div style={{ 
        width: '100%', 
        height: '100%',
        position: 'relative'
      }}>
        <Live2DCanvas 
          modelPath={modelPath} 
          audioData={audioData} 
          emotion={emotion}
          backgroundImage={backgroundImage || defaultBackgroundImage}
        />
      </div>
    </div>
  );
};

export default Live2DAvatar;