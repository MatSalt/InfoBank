import React, { useEffect, useRef } from 'react';
import * as PIXI from 'pixi.js';
import { Live2DModel } from 'pixi-live2d-display';

// PIXI를 전역 window에 노출시켜 Live2D 모델이 자동 업데이트되도록 함
window.PIXI = PIXI;

const Live2DCanvas = ({ modelPath }) => {
  const canvasRef = useRef(null);
  const pixiAppRef = useRef(null);
  const modelRef = useRef(null);

  useEffect(() => {
    // PIXI 앱 초기화
    const app = new PIXI.Application({
      view: canvasRef.current,
      autoStart: true,
      resizeTo: window,
      backgroundColor: 0xffffff,
    });
    
    pixiAppRef.current = app;

    // Live2D 모델 로드
    const loadModel = async () => {
      try {
        // 모델 로드
        const model = await Live2DModel.from(modelPath);
        
        // 모델 크기 및 위치 설정
        model.scale.set(0.3, 0.3);
        model.anchor.set(0.5, 0.5);
        model.x = app.renderer.width / 2;
        model.y = app.renderer.height / 2;
        
        // 인터랙션 활성화
        model.interactive = true;
        
        // 스테이지에 모델 추가
        app.stage.addChild(model);
        modelRef.current = model;
      } catch (e) {
        console.error('Live2D 모델 로드 실패:', e);
      }
    };

    loadModel();

    // 클린업
    return () => {
      if (pixiAppRef.current) {
        pixiAppRef.current.destroy(true);
        pixiAppRef.current = null;
      }
    };
  }, []);

  return <canvas ref={canvasRef} style={{ width: '100%', height: '100%' }} />;
};

export default Live2DCanvas;