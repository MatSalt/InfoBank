/**
 * Live2D 립싱크를 위한 오디오 프로세서 유틸리티
 * - 오디오 데이터를 분석하여 립싱크에 사용할 정규화된 값을 제공합니다.
 */

// window 객체에 AudioContext와 webkitAudioContext 타입을 명시적으로 정의
interface CustomWindow extends Window {
  AudioContext: typeof AudioContext;
  webkitAudioContext?: typeof AudioContext; // webkitAudioContext는 선택 사항
}

declare const window: CustomWindow;

export class LiveAudioProcessor {
  private _audioContext: AudioContext | null = null;
  private _analyser: AnalyserNode | null = null;
  private _dataArray: Uint8Array | null = null;
  private _lastAudioValue: number = 0;
  private _isProcessing: boolean = false;
  private _smoothingFactor: number = 0.15; // 값이 작을수록 더 빠르게 반응 (0~1)

  constructor() {
    try {
      // window 전역 객체에서 AudioContext 또는 webkitAudioContext 가져오기
      const AudioContextClass = window.AudioContext || window.webkitAudioContext;
      if (!AudioContextClass) {
        throw new Error('AudioContext is not supported in this browser.');
      }
      this._audioContext = new AudioContextClass();

      this._analyser = this._audioContext.createAnalyser();
      this._analyser.fftSize = 256;
      const bufferLength = this._analyser.frequencyBinCount;
      this._dataArray = new Uint8Array(bufferLength);
      
      // 분석기 설정
      this._analyser.smoothingTimeConstant = 0.15; // 주파수 분석 스무딩 (0~1)
      
      console.log('AudioProcessor 초기화됨');
    } catch (error) {
      console.error('오디오 컨텍스트 초기화 실패:', error);
    }
  }

  /**
   * 현재 오디오 소스를 분석기에 연결합니다.
   * @param audioSource AudioNode 또는 AudioBuffer
   */
  public connectSource(audioSource: AudioNode | AudioBuffer): void {
    if (!this._audioContext || !this._analyser) return;
    
    try {
      if (audioSource instanceof AudioNode) {
        // 오디오 노드인 경우 직접 연결
        audioSource.connect(this._analyser);
        this._analyser.connect(this._audioContext.destination);
        this._isProcessing = true;
      } else if (audioSource instanceof AudioBuffer) {
        // AudioBuffer인 경우 소스 노드 생성 후 연결
        const source = this._audioContext.createBufferSource();
        source.buffer = audioSource;
        source.connect(this._analyser);
        this._analyser.connect(this._audioContext.destination);
        source.start(0);
        this._isProcessing = true;
        
        // 오디오 재생 완료 시 처리
        source.onended = () => {
          this._isProcessing = false;
          source.disconnect();
        };
      }
      console.log('오디오 소스 연결됨');
    } catch (error) {
      console.error('오디오 소스 연결 실패:', error);
    }
  }

  /**
   * Uint8Array 바이너리 오디오 데이터로부터 립싱크 값을 추출합니다.
   * @param audioData Uint8Array 바이너리 오디오 데이터
   * @returns 정규화된 립싱크 값 (0~1)
   */
  public processAudioData(audioData: Uint8Array): number {
    if (!this._audioContext) return 0;
    
    try {
      // PCM 데이터의 RMS(Root Mean Square) 계산
      let sum = 0;
      const dataView = new DataView(audioData.buffer);
      const samples = audioData.length / 2; // 16비트 샘플 (2바이트)
      
      for (let i = 0; i < samples; i++) {
        // Int16 샘플 값 가져오기 (16비트)
        const sample = dataView.getInt16(i * 2, true); // little-endian
        sum += sample * sample;
      }
      
      // RMS 계산 및 정규화
      const rms = Math.sqrt(sum / samples);
      const normalizedValue = Math.min(1, rms / 32768); // 16비트 최대값으로 정규화
      console.log(`[AudioProcessor] rms: ${rms.toFixed(4)}, normalized: ${normalizedValue.toFixed(4)}`); // RMS 및 정규화 값 로그
      
      // 부드러운 립싱크를 위한 보간 (스무딩)
      this._lastAudioValue = this._lastAudioValue * this._smoothingFactor +
                            normalizedValue * (1 - this._smoothingFactor);

      // --- 매핑 로직 수정: 지수 매핑 사용 및 조정 ---
      // 기존 로직 주석 처리
      // let mappedValue = 1 / (1 + Math.exp(-30 * this._lastAudioValue + 5));
      // if (mappedValue < 0.1) { mappedValue = 0; } // 임계값 제거

      // 수정된 매핑: 지수값 조정 (0.25 -> 0.5)
      let mappedValue = Math.pow(this._lastAudioValue, 0.5);

      // 최종 값 범위 제한 (0.0 ~ 1.0)
      mappedValue = Math.max(0.0, Math.min(1.0, mappedValue));
      // -------------------------------------

      console.log(`[AudioProcessor] smoothed: ${this._lastAudioValue.toFixed(4)}, mapped: ${mappedValue.toFixed(4)}`); // 최종 값 로그

      return mappedValue;
    } catch (error) {
      console.error('오디오 데이터 처리 중 오류:', error);
      return 0;
    }
  }

  /**
   * 실시간 오디오 분석을 수행하고 현재 립싱크 값을 반환합니다.
   * @returns 정규화된 립싱크 값 (0~1)
   */
  public getCurrentValue(): number {
    if (!this._analyser || !this._dataArray || !this._isProcessing) {
      return 0;
    }
    
    try {
      // 주파수 데이터 가져오기
      this._analyser.getByteFrequencyData(this._dataArray);
      
      // 주파수 데이터 평균 계산
      let sum = 0;
      for (let i = 0; i < this._dataArray.length; i++) {
        sum += this._dataArray[i];
      }
      const average = sum / this._dataArray.length;
      
      // 0~1 범위로 정규화
      const normalizedValue = average / 255;
      
      // 부드러운 립싱크를 위한 보간
      this._lastAudioValue = this._lastAudioValue * this._smoothingFactor + 
                            normalizedValue * (1 - this._smoothingFactor);
                            
      // 값 증폭 (낮은 값에서도 립싱크가 보이도록)
      return Math.pow(this._lastAudioValue, 0.6);
    } catch (error) {
      console.error('오디오 분석 중 오류:', error);
      return 0;
    }
  }
  
  /**
   * 새로운 오디오 컨텍스트를 생성하고 분석기를 초기화합니다.
   */
  public reset(): void {
    try {
      if (this._audioContext) {
        this._audioContext.close().catch(console.error); // close()는 Promise를 반환할 수 있음
        this._audioContext = null; // 명시적으로 null 설정
      }

      // window 전역 객체에서 AudioContext 또는 webkitAudioContext 가져오기
      const AudioContextClass = window.AudioContext || window.webkitAudioContext;
      if (!AudioContextClass) {
        throw new Error('AudioContext is not supported in this browser.');
      }
      this._audioContext = new AudioContextClass();

      this._analyser = this._audioContext.createAnalyser();
      this._analyser.fftSize = 256;
      this._dataArray = new Uint8Array(this._analyser.frequencyBinCount);
      this._lastAudioValue = 0;
      this._isProcessing = false;
      
      console.log('AudioProcessor 초기화됨');
    } catch (error) {
      console.error('오디오 프로세서 초기화 실패:', error);
    }
  }
  
  /**
   * 립싱크 부드러움 정도를 설정합니다.
   * @param factor 스무딩 팩터 (0~1), 값이 작을수록 더 빠르게 반응
   */
  public setSmoothingFactor(factor: number): void {
    this._smoothingFactor = Math.max(0, Math.min(1, factor));
    if (this._analyser) {
      this._analyser.smoothingTimeConstant = this._smoothingFactor;
    }
  }
  
  /**
   * 리소스를 정리합니다.
   */
  public dispose(): void {
    try {
      this._isProcessing = false;
      if (this._audioContext) {
        this._audioContext.close();
        this._audioContext = null;
      }
      this._analyser = null;
      this._dataArray = null;
      console.log('AudioProcessor 해제됨');
    } catch (error) {
      console.error('AudioProcessor 해제 중 오류:', error);
    }
  }
} 