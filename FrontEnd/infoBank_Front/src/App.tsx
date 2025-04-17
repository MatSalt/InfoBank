import React from 'react';
// .tsx 확장자는 import 시 생략 가능 (모듈 해석 설정에 따라 다름)
import VoiceChatPage from './pages/VoiceChatPage';
// CSS 파일 임포트
import './index.css'; // Tailwind CSS가 포함된 메인 CSS 파일 임포트 (경로 확인 필요)

// function App(): JSX.Element { // 반환 타입 명시적 지정 가능
function App() { // 간단한 함수 선언 방식 사용
  return (
    <div className="App">
      <VoiceChatPage />
      {/* 향후 라우팅 등이 필요하면 여기에 추가 */}
    </div>
  );
}

export default App;
