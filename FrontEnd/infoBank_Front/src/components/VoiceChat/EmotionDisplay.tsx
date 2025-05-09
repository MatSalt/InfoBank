import React from 'react';
import { EMOTION_EMOJI, EmotionType } from '../../constants/emotions';

/**
 * 현재 감정 상태를 표시하는 컴포넌트
 */
interface EmotionDisplayProps {
  currentEmotion: EmotionType | string;
}

export const EmotionDisplay: React.FC<EmotionDisplayProps> = ({ currentEmotion }) => {
  const emotionEmoji = EMOTION_EMOJI[currentEmotion as EmotionType] || EMOTION_EMOJI["중립"];
  
  return (
    <div className="mb-4 p-3 bg-blue-50 rounded-lg text-center">
      <p className="text-blue-700 text-sm font-medium">
        감정 상태: {emotionEmoji} {currentEmotion}
      </p>
    </div>
  );
}; 