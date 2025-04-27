import React, { useEffect, useRef } from 'react';
import * as PIXI from 'pixi.js';
import { Live2DModel } from 'pixi-live2d-display';

// PIXI를 전역 window에 노출시켜 Live2D 모델이 자동 업데이트되도록 함
window.PIXI = PIXI;

const Live2DCanvas = ({ modelPath }) => {
  const containerRef = useRef(null);
  const pixiAppRef = useRef(null);
  const modelRef = useRef(null);

  useEffect(() => {
    if (!containerRef.current) return;

    // PIXI 앱 초기화
    const app = new PIXI.Application({
      width: containerRef.current.clientWidth,
      height: containerRef.current.clientHeight,
      backgroundColor: 0x00000000, // 투명 배경
      autoStart: true,
      antialias: true // 부드러운 렌더링을 위해 추가
    });
    
    // canvas를 컨테이너에 추가
    containerRef.current.appendChild(app.view);
    app.view.style.width = '100%';
    app.view.style.height = '100%';
    
    pixiAppRef.current = app;

    // Live2D 모델 로드
    const loadModel = async () => {
      try {
        // 모델 로드
        const model = await Live2DModel.from(modelPath);
        
        // 모델의 얼굴 부분이 잘 보이도록 위치 및 크기 조정
        // Haru 모델에 맞게 조정된 값
        const scale = Math.min(
          app.renderer.width / (model.width * 1.2),
          app.renderer.height / (model.height * 1.2)
        );
        
        // 모델 크기 설정
        model.scale.set(scale);
        model.anchor.set(0.5, 0.5);
        
        // Y축 위치를 약간 위로 조정하여 얼굴이 중앙에 오도록 함
        model.x = app.renderer.width / 2;
        model.y = (app.renderer.height / 2) - (model.height * scale * 0.1);
        
        // 인터랙션 활성화
        model.interactive = true;
        
        // 자동 모션 활성화 (idle 모션)
        if (model.internalModel?.motionManager) {
          model.internalModel.motionManager.startRandomMotion('Idle');
        }
        
        // 스테이지에 모델 추가
        app.stage.addChild(model);
        modelRef.current = model;
      } catch (e) {
        console.error('Live2D 모델 로드 실패:', e);
      }
    };

    loadModel();

    // 화면 크기 변경 감지 및 대응
    const handleResize = () => {
      if (!app || !modelRef.current) return;
      
      app.renderer.resize(containerRef.current.clientWidth, containerRef.current.clientHeight);
      
      if (modelRef.current) {
        const scale = Math.min(
          app.renderer.width / (modelRef.current.width * 1.2),
          app.renderer.height / (modelRef.current.height * 1.2)
        );
        
        // 모델 크기 업데이트
        modelRef.current.scale.set(scale);
        
        // 모델 위치 업데이트 (Y축 조정)
        modelRef.current.x = app.renderer.width / 2;
        modelRef.current.y = (app.renderer.height / 2) - (modelRef.current.height * scale * 0.1);
      }
    };

    window.addEventListener('resize', handleResize);

    // 클린업
    return () => {
      window.removeEventListener('resize', handleResize);
      
      if (pixiAppRef.current) {
        if (containerRef.current && containerRef.current.contains(app.view)) {
          containerRef.current.removeChild(app.view);
        }
        pixiAppRef.current.destroy(true, { removeView: true });
        pixiAppRef.current = null;
      }
    };
  }, [modelPath]);

  return (
    <div 
      ref={containerRef} 
      style={{ 
        width: '100%', 
        height: '100%',
        overflow: 'hidden',
        position: 'relative'
      }} 
    />
  );
};

export default Live2DCanvas;