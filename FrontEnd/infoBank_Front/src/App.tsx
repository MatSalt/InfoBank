// import VoiceChatPage from './pages/VoiceChatPage.tsx';
// import Live2DAvatar from './components/Live2DAvatar';
// CSS 파일 임포트
import './App.css';
import './index.css';
import VoiceChatWithLive2DPage from './pages/VoiceChatWithLive2D';

function App() {
  return (
    <div className="App w-full h-full min-h-screen">
      <VoiceChatWithLive2DPage />
    </div>
  );
}

export default App;
