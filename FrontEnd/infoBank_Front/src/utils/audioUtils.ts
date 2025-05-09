/**
 * 오디오 처리 관련 유틸리티 함수 모음
 */

/**
 * PCM 데이터(Int16Array)를 Float32Array로 변환
 * @param pcmData Int16Array 형식의 PCM 데이터
 * @returns Float32Array로 변환된 오디오 데이터 (-1.0 ~ 1.0 범위)
 */
export function convertPCMToFloat32(pcmData: Int16Array): Float32Array {
  const float32Data = new Float32Array(pcmData.length);
  for (let i = 0; i < pcmData.length; i++) {
    // 16비트 PCM 데이터를 -1.0 ~ 1.0 범위의 Float32로 정규화
    float32Data[i] = pcmData[i] / 32768.0;
  }
  return float32Data;
}

/**
 * Float32Array 채널 데이터를 16비트 PCM 데이터로 변환
 * @param float32Data 부동 소수점 오디오 데이터
 * @returns Int16Array로 변환된 PCM 데이터
 */
export function convertFloat32ToPCM(float32Data: Float32Array): Int16Array {
  const pcmData = new Int16Array(float32Data.length);
  for (let i = 0; i < float32Data.length; i++) {
    // -1.0 ~ 1.0 범위의 Float32 데이터를 16비트 PCM으로 변환하고 클리핑 적용
    pcmData[i] = Math.max(-32768, Math.min(32767, Math.floor(float32Data[i] * 32767)));
  }
  return pcmData;
}

/**
 * AudioContext를 생성하고 상태 확인 후 필요시 재개
 * @param audioContext 현재 AudioContext 객체
 * @returns Promise<boolean> 준비 완료 여부
 */
export async function ensureAudioContextReady(audioContext: AudioContext | null): Promise<boolean> {
  if (!audioContext) {
    return false;
  }

  try {
    if (audioContext.state === 'suspended') {
      await audioContext.resume();
      console.log("AudioContext resumed.");
    }
    return true;
  } catch (err) {
    console.error("AudioContext resume 실패:", err);
    return false;
  }
} 