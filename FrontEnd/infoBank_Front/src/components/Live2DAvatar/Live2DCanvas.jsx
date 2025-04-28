import React, { useEffect, useRef, useState, useCallback } from 'react';
import * as PIXI from 'pixi.js';
import { Live2DModel } from 'pixi-live2d-display';
import { LiveAudioProcessor } from '../../utils/LiveAudioProcessor';
import { useAudio } from '../../contexts/AudioContext';

// PIXI를 전역 window에 노출시켜 Live2D 모델이 자동 업데이트되도록 함
window.PIXI = PIXI;

const Live2DCanvas = ({ modelPath }) => {
  const containerRef = useRef(null);
  const pixiAppRef = useRef(null);
  const modelRef = useRef(null);
  const animationFrameRef = useRef(null);
  const audioProcessorRef = useRef(null);
  const [lipSyncEnabled, setLipSyncEnabled] = useState(false);
  const currentLipSyncValueRef = useRef(0);
  const [lipSyncParams, setLipSyncParams] = useState(null);
  const { audioData, isAudioPlaying } = useAudio();

  // 오디오 프로세서 초기화
  useEffect(() => {
    audioProcessorRef.current = new LiveAudioProcessor();
    
    return () => {
      if (audioProcessorRef.current) {
        audioProcessorRef.current.dispose();
      }
    };
  }, []);

  // 오디오 데이터 및 재생 상태 변경 처리
  useEffect(() => {
    console.log('[Debug] 오디오 상태 변경 감지:', { isAudioPlaying, hasAudioData: !!audioData });

    if (isAudioPlaying && audioData && audioProcessorRef.current) {
      try {
        // processAudioData 호출하여 값 계산
        const value = audioProcessorRef.current.processAudioData(audioData);
        // 상태 대신 ref에 직접 값 할당
        currentLipSyncValueRef.current = value;
        console.log('오디오 데이터 처리됨, 립싱크 값 (ref): ', currentLipSyncValueRef.current.toFixed(4));

        // lipSyncEnabled 상태는 유지 (언제 립싱크를 적용할지 결정하기 위함)
        if (!lipSyncEnabled) {
           setLipSyncEnabled(true);
        }

      } catch (error) {
        console.error('오디오 데이터 처리 오류:', error);
        setLipSyncEnabled(false);
        currentLipSyncValueRef.current = 0; // 오류 시 0으로 초기화
      }
    } else {
      // 오디오 재생 중이 아니거나 데이터가 없으면 비활성화 및 값 초기화
      if (lipSyncEnabled) { // 상태 변경 최소화를 위해 조건 추가
        console.log('[LipSync] 오디오 중지됨, 립싱크 비활성화');
        setLipSyncEnabled(false);
        // ref 값 초기화
        currentLipSyncValueRef.current = 0;

        // 오디오 중지 시 즉시 파라미터 0으로 설정 (이전 코드 유지)
        if (modelRef.current) {
          try {
            console.log('[Debug][useEffect] Force setting ParamMouthOpenY = 0');
            modelRef.current.internalModel.coreModel.setParameterValueById('ParamMouthOpenY', 0);
          } catch (error) {
            console.error('Error setting mouth parameter to 0 in useEffect:', error);
          }
        }
      }
    }
    // isAudioPlaying, lipSyncEnabled는 의존성 배열에 유지
    // audioData는 너무 자주 변경될 수 있으므로, 변경 시마다 ref를 업데이트하되
    // useEffect 자체를 너무 자주 트리거하지 않도록 audioData 자체는 배열에서 제거하거나
    // 다른 방식으로 처리하는 것을 고려해볼 수 있음 (지금은 유지)
  }, [audioData, isAudioPlaying, lipSyncEnabled]);

  // 립싱크 파라미터 업데이트 함수
  const updateLipSync = useCallback(() => {
    if (!modelRef.current) return; // 모델 없으면 아무것도 안함

    let valueToSet = 0; // 기본값 0 (입 닫힘)

    // lipSyncEnabled 상태를 확인하여 값 결정
    if (lipSyncEnabled) {
      // 상태 대신 ref에서 현재 값 가져오기
      valueToSet = currentLipSyncValueRef.current;

      // 값 범위 제한 (0.0 ~ 1.0)
      valueToSet = Math.max(0.0, Math.min(1.0, valueToSet));
    }
    // else (lipSyncEnabled가 false면) valueToSet은 0 유지

    try {
      // 항상 ParamMouthOpenY 값을 설정
      // 최종 적용 직전에 값 로깅
      console.log(`[Live2DCanvas][updateLipSync] Setting ParamMouthOpenY = ${valueToSet.toFixed(4)} (Enabled: ${lipSyncEnabled})`);
      modelRef.current.internalModel.coreModel.setParameterValueById('ParamMouthOpenY', valueToSet);

      // ParamMouthForm 부분은 Haru 모델에서 사용 안 함 (그대로 둠)
      // ...

    } catch (error) {
      console.error('립싱크 파라미터 업데이트 오류:', error);
    }
  }, [lipSyncEnabled, lipSyncParams]); // lipSyncValue 상태 의존성 제거, lipSyncEnabled, lipSyncParams 유지

  // 애니메이션 프레임 업데이트 함수 (useCallback 유지)
  const animate = useCallback(() => {
    // console.log("[Debug] animate called"); // Optional: Add log here too
    updateLipSync();
    // Schedule next frame, but store the ID in the ref
    animationFrameRef.current = requestAnimationFrame(animate);
  }, [updateLipSync]); // animate depends on updateLipSync

  // useEffect for Model Loading (NO animation start here)
  useEffect(() => {
    // ---- Mount Check ----
    let mounted = true;
    // ---------------------

    let isModelLoaded = false; // Keep this for intra-render check

    // PIXI 앱 초기화
    const app = new PIXI.Application({
      width: containerRef.current.clientWidth,
      height: containerRef.current.clientHeight,
      backgroundColor: 0x00000000, // 투명 배경
      autoStart: true,
      antialias: true // 부드러운 렌더링을 위해 추가
    });
    
    containerRef.current.appendChild(app.view);
    app.view.style.width = '100%';
    app.view.style.height = '100%';
    pixiAppRef.current = app;

    // Live2D 모델 로드
    const loadModel = async (currentApp) => { // Pass app instance
      try {
        // Check if already loaded in this cycle or previous ref still exists
        if (isModelLoaded || modelRef.current) {
          console.log('모델 로드 시도 중지: 이미 로드됨');
          return;
        }

        // Check if component unmounted before starting
        if (!mounted) {
          console.log('모델 로드 시도 중지: 컴포넌트 언마운트됨');
          return;
        }
        
        console.log('모델 로드 시작:', modelPath);
        isModelLoaded = true; // Mark as loading *within this render cycle*
        
        // Check if app exists before loading
        if (!currentApp || !currentApp.renderer) { // Use passed app instance
          console.error('PIXI 앱이 초기화되지 않았거나 제거됨 (로드 전)');
          isModelLoaded = false;
          return;
        }
        
        // --- Async Operation ---
        const model = await Live2DModel.from(modelPath);
        // -----------------------

        // ---- Post-Async Checks ----
        if (!mounted) {
          console.log('모델 로드 중단: 컴포넌트 언마운트됨 (로드 후)');
          if (model) model.destroy(); // Clean up loaded model if unmounted
          isModelLoaded = false;
          return;
        }
        if (!pixiAppRef.current || !pixiAppRef.current.renderer) { // Re-check app ref after await
            console.error('PIXI 앱이 제거됨 (로드 후)');
            if (model) model.destroy();
            isModelLoaded = false;
            return;
        }
        // ---------------------------

        if (!model) {
          console.error('모델 로드 실패: 모델이 null입니다.');
          isModelLoaded = false;
          return;
        }
        
        // 4. 모델의 width와 height가 유효한지 확인
        if (typeof model.width !== 'number' || typeof model.height !== 'number') {
          console.log('모델 크기 정보가 아직 준비되지 않음, 기본값 설정');
          // 기본 크기 설정
          model.width = model.width || 500;
          model.height = model.height || 500;
        }
        
        console.log('모델 크기:', model.width, model.height);
        
        // 모델의 얼굴 부분이 잘 보이도록 위치 및 크기 조정
        const scale = Math.min(
          pixiAppRef.current.renderer.width / (model.width * 1.2),
          pixiAppRef.current.renderer.height / (model.height * 1.2)
        );
        
        // 모델 크기 설정
        model.scale.set(scale);
        model.anchor.set(0.5, 0.5);
        
        // Y축 위치를 약간 위로 조정하여 얼굴이 중앙에 오도록 함
        model.x = pixiAppRef.current.renderer.width / 2;
        model.y = (pixiAppRef.current.renderer.height / 2) - (model.height * scale * 0.1);
        
        // 인터랙션 활성화
        model.interactive = true;

        // 자동 모션 활성화 (idle 모션) - 주석 처리하여 비활성화
        // if (model.internalModel?.motionManager) {
        //   model.internalModel.motionManager.startRandomMotion('Idle');
        // }

        // Add to stage *only if app still valid*
        pixiAppRef.current.stage.addChild(model);
        modelRef.current = model; // Set model ref *after* adding to stage

        // --- Idle 모션 그룹 비활성화 ---
        if (model.internalModel?.motionManager?.groups?.idle) {
          console.log("[Debug] Disabling Idle motion group.");
          model.internalModel.motionManager.groups.idle = undefined; // 또는 null 이나 빈 배열 [] 로 설정
        }
        // -----------------------------

        // 모델 로드 성공 후 립싱크 파라미터 설정 (Haru 모델 기준)
        // Haru.model3.json의 Groups -> LipSync -> Ids 확인
        const haruLipSyncParams = ['ParamMouthOpenY']; 
        console.log('[LipSync] 사용할 파라미터 설정:', haruLipSyncParams);
        setLipSyncParams(haruLipSyncParams); 

        // --- REMOVE animation start from here ---
        // animationFrameRef.current = requestAnimationFrame(animate); // 이 줄 제거
        // ----------------------------------------

      } catch (e) {
        console.error('Live2D 모델 로드 중 오류 발생:', e);
        isModelLoaded = false; // Reset flag on error
      }
    };

    // Initial load call
    loadModel(pixiAppRef.current); // Pass the current app instance

    // 화면 크기 변경 감지 및 대응
    const handleResize = () => {
        // Use pixiAppRef.current and modelRef.current, check they exist
        if (!pixiAppRef.current || !pixiAppRef.current.renderer || !modelRef.current) return; 
        
        pixiAppRef.current.renderer.resize(containerRef.current.clientWidth, containerRef.current.clientHeight);

        const scale = Math.min(
          pixiAppRef.current.renderer.width / (modelRef.current.width * 1.2),
          pixiAppRef.current.renderer.height / (modelRef.current.height * 1.2)
        );
        
        modelRef.current.scale.set(scale);
        modelRef.current.x = pixiAppRef.current.renderer.width / 2;
        modelRef.current.y = (pixiAppRef.current.renderer.height / 2) - (modelRef.current.height * scale * 0.1);
    };

    window.addEventListener('resize', handleResize);

    // --- Cleanup Function ---
    return () => {
      mounted = false; // Mark as unmounted
      window.removeEventListener('resize', handleResize);
      
      // --- REMOVE cancelAnimationFrame from here ---
      // 애니메이션 루프 관리는 다른 useEffect에서 하므로 여기서 취소하지 않음
      // -----------------------------------------------

      // Destroy modelRef first if it exists
      if (modelRef.current) {
        // Check if it's actually on stage before removing
        if (pixiAppRef.current && pixiAppRef.current.stage && pixiAppRef.current.stage.children.includes(modelRef.current)) {
            pixiAppRef.current.stage.removeChild(modelRef.current);
        }
        modelRef.current.destroy();
        modelRef.current = null; // Clear ref
      }
      
      // Then destroy the app
      if (pixiAppRef.current) {
        // Check containerRef exists before removing view
        if (containerRef.current && containerRef.current.contains(pixiAppRef.current.view)) {
            containerRef.current.removeChild(pixiAppRef.current.view);
        }
        pixiAppRef.current.destroy(true, { removeView: true });
        pixiAppRef.current = null; // Clear ref
      }
      
      // isModelLoaded doesn't need resetting here as it's local to useEffect
    };
  }, [modelPath]); // Only depends on modelPath

  // NEW useEffect for managing animation loop
  useEffect(() => {
    // Start animation only if model is loaded AND the animate function is ready
    if (modelRef.current && pixiAppRef.current) {
        console.log("[Debug] Starting animation loop.");
        // Cancel any previous loop just in case (e.g., if animate function updates rapidly)
        if (animationFrameRef.current) {
            cancelAnimationFrame(animationFrameRef.current);
        }
        // Start the loop with the current (latest) animate function
        animationFrameRef.current = requestAnimationFrame(animate);
    } else {
        // Optional: Log if animation doesn't start because model isn't ready
        // console.log("[Debug] Animation loop not started: Model or App not ready.");
    }

    // Cleanup function for THIS useEffect: Stop the loop when component unmounts OR when animate function changes
    return () => {
        console.log("[Debug] Stopping animation loop.");
        if (animationFrameRef.current) {
            cancelAnimationFrame(animationFrameRef.current);
            animationFrameRef.current = null; // Clear ref
        }
    };
  }, [animate]); // Key dependency: Run this effect when the 'animate' function reference changes

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