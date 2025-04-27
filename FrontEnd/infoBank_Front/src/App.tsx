// import VoiceChatPage from './pages/VoiceChatPage.tsx';
import Live2DAvatar from './components/Live2DAvatar';
// CSS 파일 임포트
import './App.css';
import './index.css';

function App() {
  return (
    <div className="App w-full h-full min-h-screen flex flex-col items-center justify-center bg-gray-100">
      <h1 className="text-2xl font-bold mb-4">Live2D 아바타 데모</h1>
      <div className="w-full max-w-4xl h-[80vh]">
        <Live2DAvatar />
      </div>
    </div>
  );
}

export default App;
