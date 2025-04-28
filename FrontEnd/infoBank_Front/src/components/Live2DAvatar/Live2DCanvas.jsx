import React, { useEffect, useRef, useState, useCallback } from 'react';
import * as PIXI from 'pixi.js';
import { Live2DModel } from 'pixi-live2d-display';
// import { LiveAudioProcessor } from '../../utils/LiveAudioProcessor'; // 제거
import { useAudio } from '../../contexts/AudioContext';

// PIXI를 전역 window에 노출시켜 Live2D 모델이 자동 업데이트되도록 함
window.PIXI = PIXI;

const Live2DCanvas = ({ modelPath }) => {
  const containerRef = useRef(null);
  const pixiAppRef = useRef(null);
  const modelRef = useRef(null);
  const animationFrameRef = useRef(null);
  // const audioProcessorRef = useRef(null); // 제거
  const dataArrayRef = useRef(null); // AnalyserNode 데이터 배열 ref
  const currentLipSyncValueRef = useRef(0); // 스무딩된 값 저장용 ref
  const currentMouthFormValueRef = useRef(1); // ParamMouthForm 스무딩 값 저장용 ref (초기값 1)
  // const [lipSyncEnabled, setLipSyncEnabled] = useState(false); // isAudioPlaying으로 대체
  // const [lipSyncParams, setLipSyncParams] = useState(null); // 모델 로드 시 직접 설정

  // isAudioPlaying과 analyserNode를 컨텍스트에서 가져옴
  const { isAudioPlaying, analyserNode } = useAudio();

  // 오디오 프로세서 초기화 제거
  // useEffect(() => { ... }, []);

  // AnalyserNode 준비 시 데이터 배열 생성
  useEffect(() => {
    if (analyserNode && !dataArrayRef.current) {
      // AnalyserNode의 frequencyBinCount 크기에 맞춰 Uint8Array 생성
      // frequencyBinCount는 fftSize의 절반
      dataArrayRef.current = new Uint8Array(analyserNode.frequencyBinCount);
      console.log('[Live2DCanvas] AnalyserNode data array initialized with size:', analyserNode.frequencyBinCount);
    }
  }, [analyserNode]); // analyserNode가 변경될 때 실행

  // 오디오 데이터 및 재생 상태 변경 처리 useEffect 제거 (updateLipSync에서 직접 처리)
  // useEffect(() => { ... }, [audioData, isAudioPlaying, lipSyncEnabled]);

  // 립싱크 파라미터 업데이트 함수 수정
  const updateLipSync = useCallback(() => {
    // 필요한 요소들이 준비되지 않았으면 중단
    if (!modelRef.current || !modelRef.current.internalModel?.coreModel || !analyserNode || !dataArrayRef.current) {
        // 입 모양 초기화 (모델 로드 전에 호출될 수 있으므로 안전하게 처리)
        if (modelRef.current?.internalModel?.coreModel) {
             try {
                 modelRef.current.internalModel.coreModel.setParameterValueById('ParamMouthOpenY', 0);
             } catch {}
        }
        return;
    }

    let valueToSet = 0; // 기본값 (입 닫힘)

    // 오디오가 재생 중일 때만 분석 수행
    if (isAudioPlaying) {
      // 시간 영역 데이터 가져오기 (파형 분석)
      analyserNode.getByteTimeDomainData(dataArrayRef.current);

      // RMS(Root Mean Square) 계산으로 볼륨 측정 (0 ~ 1 범위로 정규화된 값)
      let sumSquares = 0.0;
      for (const amplitude of dataArrayRef.current) {
        // 데이터는 Uint8 (0~255), 128을 0점으로 간주하여 -1 ~ +1 범위로 정규화
        const normalizedAmplitude = (amplitude / 128.0) - 1.0;
        sumSquares += normalizedAmplitude * normalizedAmplitude;
      }
      const rms = Math.sqrt(sumSquares / dataArrayRef.current.length);

      // RMS 값(일반적으로 0 ~ 0.7 범위)을 립싱크 값(0 ~ 1)으로 매핑
      // 증폭 계수(예: 1.5 또는 2.0)를 조절하여 입 움직임 크기 조절
      const amplification = 5.0; // 값 증가 (예: 1.8 -> 2.8)
      valueToSet = Math.min(1.0, rms * amplification); // 1.0을 넘지 않도록 제한

      // 스무딩 적용 (선택 사항, 값을 부드럽게 변화시킴)
      const smoothingFactor = 0.65; // 값 감소 (예: 0.7 -> 0.5)
      currentLipSyncValueRef.current = currentLipSyncValueRef.current * smoothingFactor + valueToSet * (1 - smoothingFactor);
      valueToSet = currentLipSyncValueRef.current;

      // 디버깅 로그 (필요시 활성화)
      // console.log(`[Live2DCanvas][updateLipSync] RMS: ${rms.toFixed(4)}, Smoothed Value: ${valueToSet.toFixed(4)}`);

    } else {
       // 오디오 재생 중이 아닐 때는 스무딩 값도 0으로 초기화
       currentLipSyncValueRef.current = 0;
       valueToSet = 0;
    }

    try {
      // 계산된 값으로 입 모양 파라미터 설정
      modelRef.current.internalModel.coreModel.setParameterValueById('ParamMouthOpenY', valueToSet);

      // ParamMouthForm을 랜덤하게 설정 (-1 ~ 1) - 오디오 재생 중일 때는 랜덤, 멈추면 1
      // const randomMouthFormValue = isAudioPlaying ? (Math.random() * 2) - 1 : 1;
      // modelRef.current.internalModel.coreModel.setParameterValueById('ParamMouthForm', randomMouthFormValue);

      // ParamMouthForm 스무딩 적용
      const mouthFormSmoothingFactor = 0.25; // 스무딩 강도 (0~1, 작을수록 느림)
      let targetMouthFormValue;
      if (valueToSet >= 0.1) {
        // 목표 랜덤 값 생성 (-1 ~ 1)
        // 매번 생성하기보다 일정 간격으로 목표값을 바꾸는 것도 고려 가능
        targetMouthFormValue = (Math.random() * 2) - 1;
      } else {
        // 오디오 멈추면 목표값 1
        targetMouthFormValue = 1;
      }
      // 현재 값에서 목표 값으로 스무딩
      currentMouthFormValueRef.current = currentMouthFormValueRef.current * (1 - mouthFormSmoothingFactor) + targetMouthFormValue * mouthFormSmoothingFactor;
      modelRef.current.internalModel.coreModel.setParameterValueById('ParamMouthForm', currentMouthFormValueRef.current);

    } catch (error) {
      // 파라미터 설정 오류는 자주 발생할 수 있으므로, 에러 레벨을 낮추거나 필터링 고려
      // console.error('립싱크 파라미터 업데이트 오류:', error);
    }
  }, [isAudioPlaying, analyserNode]); // isAudioPlaying, analyserNode 변경 시 함수 재생성

  // 애니메이션 프레임 업데이트 함수 (변경 없음)
  const animate = useCallback(() => {
    updateLipSync();
    animationFrameRef.current = requestAnimationFrame(animate);
  }, [updateLipSync]);

  // 모델 로딩 useEffect (파라미터 설정 부분 외 변경 없음)
  useEffect(() => {
    let mounted = true;
    let isModelLoaded = false;

    const app = new PIXI.Application({
      width: containerRef.current.clientWidth,
      height: containerRef.current.clientHeight,
      backgroundColor: 0x00000000, // 투명 배경
      autoStart: true,
      antialias: true
    });

    // containerRef가 유효한지 확인 후 view 추가
    if (containerRef.current) {
        containerRef.current.appendChild(app.view);
        app.view.style.width = '100%';
        app.view.style.height = '100%';
        pixiAppRef.current = app;
    } else {
        console.error("Container ref is not available to append PIXI view.");
        app.destroy(true, { removeView: true }); // 앱 정리
        return; // 조기 종료
    }

    const loadModel = async (currentApp) => {
      try {
        if (isModelLoaded || modelRef.current) return;
        if (!mounted) return;

        console.log('모델 로드 시작:', modelPath);
        isModelLoaded = true;

        if (!currentApp || !currentApp.renderer) {
          console.error('PIXI 앱이 초기화되지 않았거나 제거됨 (로드 전)');
          isModelLoaded = false;
          return;
        }

        const model = await Live2DModel.from(modelPath);

        if (!mounted) {
          console.log('모델 로드 중단: 컴포넌트 언마운트됨 (로드 후)');
          if (model) model.destroy();
          isModelLoaded = false;
          return;
        }
        if (!pixiAppRef.current || !pixiAppRef.current.renderer) {
            console.error('PIXI 앱이 제거됨 (로드 후)');
            if (model) model.destroy();
            isModelLoaded = false;
            return;
        }

        if (!model) {
          console.error('모델 로드 실패: 모델이 null입니다.');
          isModelLoaded = false;
          return;
        }

        if (typeof model.width !== 'number' || typeof model.height !== 'number') {
          model.width = model.width || 500;
          model.height = model.height || 500;
        }
        console.log('모델 크기:', model.width, model.height);

        const scale = Math.min(
          pixiAppRef.current.renderer.width / (model.width * 1.2),
          pixiAppRef.current.renderer.height / (model.height * 1.2)
        );

        model.scale.set(scale);
        model.anchor.set(0.5, 0.5);
        model.x = pixiAppRef.current.renderer.width / 2;
        model.y = (pixiAppRef.current.renderer.height / 2) - (model.height * scale * 0.1);
        model.interactive = true;

        // --- Idle 모션 그룹 비활성화 유지 ---
        if (model.internalModel?.motionManager?.groups?.idle) {
          console.log("[Debug] Disabling Idle motion group.");
          model.internalModel.motionManager.groups.idle = undefined;
        }
        // ---------------------------------

        // 스테이지에 추가 전에 앱 유효성 재확인
        if (pixiAppRef.current && pixiAppRef.current.stage) {
            pixiAppRef.current.stage.addChild(model);
            modelRef.current = model;
        } else {
            console.error("Cannot add model to stage, Pixi App or stage not available.");
            model.destroy(); // 생성된 모델 정리
            isModelLoaded = false;
            return;
        }

        // 모델 로드 성공 후 립싱크 파라미터 직접 설정
        const haruLipSyncParams = ['ParamMouthOpenY'];
        console.log('[LipSync] 사용할 파라미터:', haruLipSyncParams);

      } catch (e) {
        console.error('Live2D 모델 로드 중 오류 발생:', e);
        isModelLoaded = false;
      }
    };

    loadModel(pixiAppRef.current);

    const handleResize = () => {
        if (!pixiAppRef.current || !pixiAppRef.current.renderer || !modelRef.current) return;
        // containerRef.current가 유효한지 확인
        if (!containerRef.current) return;

        pixiAppRef.current.renderer.resize(containerRef.current.clientWidth, containerRef.current.clientHeight);

        // 모델 크기 및 위치 재계산 (모델 로드 완료 후)
        if (modelRef.current.width && modelRef.current.height) {
            const scale = Math.min(
              pixiAppRef.current.renderer.width / (modelRef.current.width * 1.2),
              pixiAppRef.current.renderer.height / (modelRef.current.height * 1.2)
            );
            modelRef.current.scale.set(scale);
            modelRef.current.x = pixiAppRef.current.renderer.width / 2;
            modelRef.current.y = (pixiAppRef.current.renderer.height / 2) - (modelRef.current.height * scale * 0.1);
        }
    };

    window.addEventListener('resize', handleResize);

    return () => {
      mounted = false;
      window.removeEventListener('resize', handleResize);

      if (modelRef.current) {
        // 모델 제거 전 스테이지 확인
        if (pixiAppRef.current?.stage?.children.includes(modelRef.current)) {
            pixiAppRef.current.stage.removeChild(modelRef.current);
        }
        modelRef.current.destroy({ children: true }); // 내부 리소스도 함께 파괴
        modelRef.current = null;
      }

      if (pixiAppRef.current) {
        // 뷰 제거 전 컨테이너 확인
        if (containerRef.current && pixiAppRef.current.view && containerRef.current.contains(pixiAppRef.current.view)) {
            containerRef.current.removeChild(pixiAppRef.current.view);
        }
        pixiAppRef.current.destroy(true, { children: true, texture: true, baseTexture: true }); // 모든 리소스 파괴
        pixiAppRef.current = null;
      }
    };
  }, [modelPath]);

  // 애니메이션 루프 관리 useEffect (변경 없음)
  useEffect(() => {
    if (modelRef.current && pixiAppRef.current) {
        console.log("[Debug] Starting animation loop.");
        if (animationFrameRef.current) {
            cancelAnimationFrame(animationFrameRef.current);
        }
        animationFrameRef.current = requestAnimationFrame(animate);
    }
    return () => {
        console.log("[Debug] Stopping animation loop.");
        if (animationFrameRef.current) {
            cancelAnimationFrame(animationFrameRef.current);
            animationFrameRef.current = null;
        }
    };
  }, [animate]);

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