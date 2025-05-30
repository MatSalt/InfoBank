import React, { useEffect, useRef, useState, useCallback } from 'react';
import * as PIXI from 'pixi.js';
import { Live2DModel } from 'pixi-live2d-display';
import { useAudio } from '../../contexts/AudioContext';

// 로거 생성 (JS 파일에서 사용하는 간단한 로거)
const LOG_LEVEL = {
  ERROR: 0,
  WARN: 1,
  INFO: 2,
  DEBUG: 3,
  VERBOSE: 4
};

// 프로덕션 여부 확인 (Vite에서는 import.meta.env.PROD로 확인)
const IS_PRODUCTION = import.meta.env.PROD === true;
const CURRENT_LOG_LEVEL = IS_PRODUCTION ? LOG_LEVEL.INFO : LOG_LEVEL.VERBOSE;

const logger = {
  error: (message, ...args) => console.error(`[Live2DCanvas] ${message}`, ...args),
  warn: (message, ...args) => CURRENT_LOG_LEVEL >= LOG_LEVEL.WARN && console.warn(`[Live2DCanvas] ${message}`, ...args),
  info: (message, ...args) => CURRENT_LOG_LEVEL >= LOG_LEVEL.INFO && console.info(`[Live2DCanvas] ${message}`, ...args),
  debug: (message, ...args) => CURRENT_LOG_LEVEL >= LOG_LEVEL.DEBUG && console.log(`[Live2DCanvas:debug] ${message}`, ...args),
  verbose: (message, ...args) => CURRENT_LOG_LEVEL >= LOG_LEVEL.VERBOSE && console.log(`[Live2DCanvas:verbose] ${message}`, ...args)
};

// PIXI를 전역 window에 노출시켜 Live2D 모델이 자동 업데이트되도록 함
window.PIXI = PIXI;

// 감정에 따른 표정 매핑
const EMOTION_TO_EXPRESSION = {
  "중립": "F01",      // 기본 표정
  "기쁨": "F02",      // 기쁨
  "화남": "F03",      // 화남
  "짜증": "F03",      // 화남과 동일
  "속상함": "F04",    // 속상함
  "슬픔": "F04",      // 속상함과 동일
  "행복": "F05",      // 행복
  "놀라움": "F06",    // 놀람
  "부끄러움": "F07",  // 부끄러움
  "싫증": "F08",      // 싫증
  "귀찮음": "F08"     // 싫증과 동일
};

const Live2DCanvas = ({ modelPath, emotion = "중립", backgroundImage }) => {
  const containerRef = useRef(null);
  const pixiAppRef = useRef(null);
  const modelRef = useRef(null);
  const animationFrameRef = useRef(null);
  const dataArrayRef = useRef(null); // AnalyserNode 데이터 배열 ref
  const currentLipSyncValueRef = useRef(0); // 스무딩된 값 저장용 ref
  const currentMouthFormValueRef = useRef(1); // ParamMouthForm 스무딩 값 저장용 ref (초기값 1)
  const currentEmotionRef = useRef("중립"); // 현재 적용된 감정 상태 ref
  
  // 현재 표정 이름 상태 추가
  const [currentExpression, setCurrentExpression] = useState("F08");

  // isAudioPlaying과 analyserNode를 컨텍스트에서 가져옴
  const { isAudioPlaying, analyserNode } = useAudio();

  // AnalyserNode 준비 시 데이터 배열 생성
  useEffect(() => {
    if (analyserNode && !dataArrayRef.current) {
      // AnalyserNode의 frequencyBinCount 크기에 맞춰 Uint8Array 생성
      // frequencyBinCount는 fftSize의 절반
      dataArrayRef.current = new Uint8Array(analyserNode.frequencyBinCount);
      logger.info('AnalyserNode data array initialized with size:', analyserNode.frequencyBinCount);
    }
  }, [analyserNode]); // analyserNode가 변경될 때 실행

  // 감정 변경 감지 및 표정 업데이트
  useEffect(() => {
    if (emotion !== currentEmotionRef.current) {
      currentEmotionRef.current = emotion;
      updateExpression(emotion);
    }
  }, [emotion]);

  // 표정 업데이트 함수
  const updateExpression = useCallback((emotion) => {
    if (!modelRef.current) return;
    
    // 감정에 해당하는 표정 이름 가져오기
    const expressionName = EMOTION_TO_EXPRESSION[emotion] || "F08";
    
    try {
      // 모델에 표정 적용
      if (modelRef.current.internalModel) {
        // 표정 적용 시도
        logger.info(`표정 변경: ${emotion} -> ${expressionName}`);
        
        // expressionManager 확인
        const expressionManager = modelRef.current.internalModel.motionManager?.expressionManager;
        
        if (expressionManager) {
          // 표정 직접 적용
          try {
            // expressionManager.setExpression 직접 호출
            expressionManager.setExpression(expressionName);
            setCurrentExpression(expressionName);
          } catch (expError) {
            logger.error('표정 적용 실패:', expError);
            
            // 실패 시 첫 번째 표정 시도
            try {
              expressionManager.setExpression(0);
              setCurrentExpression(expressionName);
            } catch (expError2) {
              logger.error('표정 적용 재시도 실패:', expError2);
            }
          }
        } else {
          logger.warn('모델의 expressionManager가 초기화되지 않았습니다.');
        }
      } else {
        logger.warn('모델이 초기화되지 않았습니다.');
      }
    } catch (error) {
      logger.error('표정 업데이트 오류:', error);
    }
  }, []);

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

      // 디버깅 로그 제거 (프로덕션 환경에서는 표시 안 함)
    } else {
       // 오디오 재생 중이 아닐 때는 스무딩 값도 0으로 초기화
       currentLipSyncValueRef.current = 0;
       valueToSet = 0;
    }

    try {
      // 계산된 값으로 입 모양 파라미터 설정
      modelRef.current.internalModel.coreModel.setParameterValueById('ParamMouthOpenY', valueToSet);

      // ParamMouthForm 스무딩 적용
      const mouthFormSmoothingFactor = 0.2; // 스무딩 강도 (0~1, 작을수록 느림)
      let targetMouthFormValue;
      if (valueToSet >= 0.1) {
        // 목표 랜덤 값 생성 (-1 ~ 1)
        targetMouthFormValue = (Math.random() * 2) - 1;
      } else {
        // 오디오 멈추면 목표값 1
        targetMouthFormValue = 1;
      }
      // 현재 값에서 목표 값으로 스무딩
      currentMouthFormValueRef.current = currentMouthFormValueRef.current * (1 - mouthFormSmoothingFactor) + targetMouthFormValue * mouthFormSmoothingFactor;
      modelRef.current.internalModel.coreModel.setParameterValueById('ParamMouthForm', currentMouthFormValueRef.current);

    } catch (error) {
      // 파라미터 설정 오류는 자주 발생할 수 있으므로, verbose 레벨 로그로 설정
      logger.verbose('립싱크 파라미터 업데이트 오류:', error);
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
      transparent: true, // 투명도 활성화
      clearBeforeRender: true, // 렌더링 전 화면 지우기
      autoStart: true,
      antialias: true
    });

    // containerRef가 유효한지 확인 후 view 추가
    if (containerRef.current) {
        containerRef.current.appendChild(app.view);
        app.view.style.width = '100%';
        app.view.style.height = '100%';
        app.renderer.view.style.position = 'absolute'; // 위치 설정
        app.renderer.view.style.display = 'block'; // 블록 표시로 설정
        // 렌더러 투명도 설정 추가
        app.renderer.backgroundColor = 0x000000;
        app.renderer.backgroundAlpha = 0;
        pixiAppRef.current = app;
    } else {
        logger.error("Container ref is not available to append PIXI view.");
        app.destroy(true, { removeView: true }); // 앱 정리
        return; // 조기 종료
    }

    const loadModel = async (currentApp) => {
      try {
        if (isModelLoaded || modelRef.current) return;
        if (!mounted) return;

        logger.info('모델 로드 시작:', modelPath);
        isModelLoaded = true;

        if (!currentApp || !currentApp.renderer) {
          logger.error('PIXI 앱이 초기화되지 않았거나 제거됨 (로드 전)');
          isModelLoaded = false;
          return;
        }

        const model = await Live2DModel.from(modelPath);

        if (!mounted) {
          logger.debug('모델 로드 중단: 컴포넌트 언마운트됨 (로드 후)');
          if (model) model.destroy();
          isModelLoaded = false;
          return;
        }
        if (!pixiAppRef.current || !pixiAppRef.current.renderer) {
            logger.error('PIXI 앱이 제거됨 (로드 후)');
            if (model) model.destroy();
            isModelLoaded = false;
            return;
        }

        if (!model) {
          logger.error('모델 로드 실패: 모델이 null입니다.');
          isModelLoaded = false;
          return;
        }

        if (typeof model.width !== 'number' || typeof model.height !== 'number') {
          model.width = model.width || 500;
          model.height = model.height || 500;
        }
        logger.debug('모델 크기:', model.width, model.height);

        // 모델 크기 조정 - 상반신만 보이도록 스케일 조정
        const scale = Math.min(
          pixiAppRef.current.renderer.width / (model.width * 0.8), // 0.8로 변경하여 모델을 더 크게 표시
          pixiAppRef.current.renderer.height / (model.height * 0.8) // 0.8로 변경하여 모델을 더 크게 표시
        ) * 1.5; // 추가 스케일 적용

        model.scale.set(scale);
        model.anchor.set(0.5, 0.3); // 앵커 포인트를 위쪽으로 이동 (0.5, 0.3)
        model.x = pixiAppRef.current.renderer.width / 2;
        model.y = (pixiAppRef.current.renderer.height / 2) + 80; // 80픽셀 아래로 이동
        model.interactive = true;

        // --- Idle 모션 그룹 비활성화 유지 ---
        if (model.internalModel?.motionManager?.groups?.idle) {
          logger.debug("Disabling Idle motion group.");
          model.internalModel.motionManager.groups.idle = undefined;
        }
        // ---------------------------------

        // 스테이지에 추가 전에 앱 유효성 재확인
        if (pixiAppRef.current && pixiAppRef.current.stage) {
            // 스테이지 배경 투명하게 설정
            pixiAppRef.current.stage.alpha = 1;
            pixiAppRef.current.stage.addChild(model);
            modelRef.current = model;
            
            // 초기 감정 적용
            updateExpression(currentEmotionRef.current);
        } else {
            logger.error("Cannot add model to stage, Pixi App or stage not available.");
            model.destroy(); // 생성된 모델 정리
            isModelLoaded = false;
            return;
        }

        // 모델 로드 직후 디버깅 정보 추가
        logger.debug('모델 크기:', model.width, model.height);
        
        // 모델 객체 구조 살펴보기 (디버깅)
        try {
          logger.verbose('모델 객체 정보:');
          logger.verbose('- internalModel 존재:', !!model.internalModel);
          logger.verbose('- motionManager 존재:', !!model.internalModel?.motionManager);
          logger.verbose('- expressionManager 존재:', !!model.internalModel?.motionManager?.expressionManager);
          
          // 표정 관련 속성 확인 - 간소화
          if (model.internalModel?.motionManager?.expressionManager) {
            // 디버깅 목적으로만 확인 (로깅 없음)
            const hasExpressions = model.internalModel.motionManager.expressionManager.definitions.length > 0;
          }
        } catch (e) {
          logger.warn('모델 디버깅 정보 출력 중 오류:', e);
        }

        // 모델 로드 성공 후 립싱크 파라미터 직접 설정
        const haruLipSyncParams = ['ParamMouthOpenY'];
        logger.info('사용할 립싱크 파라미터:', haruLipSyncParams);

        // 모델 크기 로그 (기존 코드)
        logger.debug('모델 크기:', model.width, model.height);

        // 기본 애니메이션 비활성화 (Idle 모션 그룹)
        try {
          logger.debug('Disabling Idle motion group.');
          model.internalModel.motionManager.stopAllMotions();
        } catch (e) {
          logger.warn('Idle 모션 비활성화 오류:', e);
        }

        // 표정 관련 로깅 간소화
        try {
          if (model.internalModel.motionManager?.expressionManager) {
            // 기본 표정 설정
            updateExpression(currentEmotionRef.current);
          } else {
            logger.warn('모델에 expressionManager가 없습니다.');
          }
        } catch (e) {
          logger.error('표정 설정 오류:', e);
        }

      } catch (e) {
        logger.error('Live2D 모델 로드 중 오류 발생:', e);
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
              pixiAppRef.current.renderer.width / (modelRef.current.width * 0.8),
              pixiAppRef.current.renderer.height / (modelRef.current.height * 0.8)
            ) * 1.5;
            modelRef.current.scale.set(scale);
            modelRef.current.anchor.set(0.5, 0.3);
            modelRef.current.x = pixiAppRef.current.renderer.width / 2;
            modelRef.current.y = (pixiAppRef.current.renderer.height / 2) + 80; // 80픽셀 아래로 이동
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
  }, [modelPath, updateExpression]); // updateExpression 의존성 추가

  // 애니메이션 루프 관리 useEffect (변경 없음)
  useEffect(() => {
    if (modelRef.current && pixiAppRef.current) {
        logger.debug("Starting animation loop.");
        if (animationFrameRef.current) {
            cancelAnimationFrame(animationFrameRef.current);
        }
        animationFrameRef.current = requestAnimationFrame(animate);
    }
    return () => {
        logger.debug("Stopping animation loop.");
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
        position: 'relative',
        backgroundImage: backgroundImage ? `url(${backgroundImage})` : 'none',
        backgroundSize: 'cover',
        backgroundPosition: 'center',
        backgroundRepeat: 'no-repeat'
      }}
    />
  );
};

export default Live2DCanvas;