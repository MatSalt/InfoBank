# InfoBank 프로젝트 - 42서울 추억 공유 아바타

## 왜 이 프로젝트를 시작하게 되었는가?
infoBank의 채용 연계 과제로 가상 아바타 대화 시스템 개발을 시작했습니다. 하지만 단순한 기술 구현을 넘어, 42서울에서의 소중한 경험과 추억들을 잊히지 않게 담아내고 싶었습니다. 저와 동료들의 빛나는 순간들이 미래의 새로운 42서울 학생들에게도 이어지길 바라는 마음으로, 42서울 학생 페르소나를 가진 '추억 공유 아바타'를 만들게 되었습니다. 이 아바타가 우리가 함께했던 즐거운 기억들을 다시 떠올리게 하는 매개체가 되기를 소망합니다.

## 이 프로젝트는 어떤 문제를 해결할 수 있는가?
"42서울 추억 공유 아바타"는 다음과 같은 가치를 제공합니다.
- 42서울 학생들의 소중한 추억들을 담은 아바타
- 42서울 학생들이 대화하면서 지난 추억들을 곱씹을 수 있게 하는 아바타
- 앞으로의 새로운 기수들과 42서울에 남겨진 추억들을 공유할 수 있는 아바타

단순한 대화 시스템을 넘어, 42서울의 따뜻한 기억과 문화를 담아내고 공유하는 것을 목표로 합니다.

## 이 프로젝트의 특장점은 무엇인가?
- 웹 기반으로 구현된, 사용자 중심의 편의성
- 생동감 있는 대화를 위한, 개성 있는 페르소나
- 구글 백본 네트워크를 활용한, 빠른 응답속도
- 풍부한 감정 전달을 위한, 표정 변화
- 유대감 형성을 위한, RAG로 되살린 기억
- 실제 대화 같은, 자연스러운 인터럽트

## 목차

*   [프로젝트 개요](#프로젝트-개요)
*   [기술 스택](#기술-스택)
    *   [프론트엔드](#프론트엔드-infobank_front)
    *   [백엔드](#백엔드)
*   [프로젝트 구조](#프로젝트-구조)
    *   [프론트엔드](#프론트엔드-구조)
    *   [백엔드](#백엔드-구조)
*   [주요 기능](#주요-기능)
*   [설치 및 실행](#설치-및-실행)
    *   [사전 요구사항](#사전-요구사항)
    *   [프론트엔드 설정](#프론트엔드-설정-frontendinfobank_front)
    *   [백엔드 설정](#백엔드-설정-backend)
*   [사용 방법](#사용-방법)
*   [API 엔드포인트 (백엔드)](#api-엔드포인트-백엔드)
*   [라이선스](#라이선스)
*   [기여 방법](#기여-방법)
*   [연락처](#연락처)

## 프로젝트 개요

이 프로젝트는 프론트엔드에서는 사용자가 음성으로 질문하거나 명령을 내릴 수 있으며, Live2D 아바타를 통해 시각적인 피드백과 감정 표현을 제공합니다. 백엔드에서는 사용자의 음성을 실시간으로 텍스트로 변환(STT)하고, 변환된 텍스트를 기반으로 RAG (Retrieval Augmented Generation) 서비스를 통해 관련 정보를 검색하며, LLM(대규모 언어 모델)을 사용하여 답변을 생성하고 사용자의 감정을 분석합니다. 생성된 답변은 다시 음성으로 변환(TTS)되어 사용자에게 전달됩니다.


## 기술 스택

### 프론트엔드 (`infobank_front`)

*   **언어**: TypeScript
*   **UI 프레임워크/라이브러리**: React 19
*   **빌드 도구**: Vite
*   **스타일링**: Tailwind CSS, 일반 CSS (`App.css`, `index.css`)
*   **그래픽/애니메이션**:
    *   PixiJS (`pixi.js`)
    *   Live2D: `pixi-live2d-display` (Live2D 아바타 렌더링)
    *   Three.js (현재 직접 사용되지 않으나, 의존성에 포함)
*   **상태 관리**: React Context API (`src/contexts/AudioContext.tsx`)
*   **라우팅**: 단일 페이지 애플리케이션 (`src/pages/VoiceChatWithLive2D.tsx` 중심)
*   **핵심 로직**:
    *   커스텀 훅: `src/hooks/useVoiceConversation.tsx` (음성 대화 로직 총괄)
    *   오디오 처리: `src/utils/LiveAudioProcessor.ts`, `src/utils/audioUtils.ts`
    *   웹소켓 통신: `src/utils/webSocketUtils.ts`
*   **린팅**: ESLint, TypeScript-ESLint
*   **패키지 매니저**: npm

### 백엔드

*   **언어**: Python 3.12
*   **웹 프레임워크**: FastAPI
*   **애플리케이션 서버**: Uvicorn (개발), Gunicorn (배포용 Dockerfile에 명시)
*   **데이터베이스/벡터 스토어**: ChromaDB (`app/data/vector_db/`, `app/services/rag_service/vector_store.py`) - RAG 서비스용
*   **AI/ML 서비스 및 라이브러리**:
    *   **LLM**: Google Generative AI (Gemini 1.5) - `app/services/llm_service.py`
    *   **감정 분석**: LLM 기반 감정 분석 - `app/services/llm_emotion_service.py`
    *   **STT (Speech-to-Text)**: Google Cloud Speech-to-Text - `app/services/stt_service.py`
    *   **TTS (Text-to-Speech)**: Google Cloud Text-to-Speech - `app/services/tts_service.py`
    *   **RAG (Retrieval Augmented Generation)**: Langchain, ChromaDB - `app/services/rag_service/`
        *   임베딩: `app/services/rag_service/embeddings.py` (Google `text-embedding-004` 모델 사용)
        *   프롬프트 빌더: `app/services/rag_service/prompt_builder.py`
    *   Google Cloud AI Platform (의존성 포함)
*   **데이터 검증/설정**: Pydantic, Pydantic-Settings (`app/core/config.py`)
*   **비동기 처리/통신**:
    *   WebSockets: `app/utils/websocket_utils.py`, `app/routers/voice_chat_router.py`
    *   HTTPX (비동기 HTTP 클라이언트)
*   **컨테이너화**: Docker (`Dockerfile`)

## 프로젝트 구조

### 프론트엔드 구조 (`FrontEnd/infoBank_Front/src/`)

*   **`main.tsx`**: 애플리케이션 진입점, React 루트 렌더링.
*   **`App.tsx`**: 최상위 컴포넌트, `VoiceChatWithLive2DPage` 렌더링.
*   **`pages/`**:
    *   `VoiceChatWithLive2D.tsx`: 음성 채팅 및 Live2D 아바타 인터페이스 페이지.
*   **`components/`**: 재사용 가능한 UI 컴포넌트.
    *   `Live2DAvatar/`: Live2D 아바타 렌더링 관련 컴포넌트 (`Live2DCanvas.jsx`).
    *   `VoiceChat/`: 음성 채팅 UI 관련 컴포넌트들 (예: `ControlButton.tsx`, `TranscriptDisplay.tsx`, `StatusMessage.tsx`).
*   **`hooks/`**:
    *   `useVoiceConversation.tsx`: 음성 대화의 핵심 로직(오디오 녹음, 웹소켓 통신, 상태 관리 등)을 담고 있는 커스텀 훅.
*   **`contexts/`**:
    *   `AudioContext.tsx`: 오디오 관련 상태 및 기능을 제공하는 컨텍스트.
*   **`utils/`**: 유틸리티 함수 모음.
    *   `audioUtils.ts`: 오디오 처리 관련 유틸리티.
    *   `webSocketUtils.ts`: 웹소켓 통신 설정 및 관리.
    *   `LiveAudioProcessor.ts`: 실시간 오디오 스트림 처리.
    *   `logger.ts`: 로깅 유틸리티.
*   **`constants/`**: 애플리케이션 전역 상수.
    *   `env.ts`: 환경 변수 관련 상수.
    *   `emotions.ts`: 감정 표현 관련 상수.
*   **`types/`**: TypeScript 타입 정의.
    *   `voiceConversationTypes.ts`: 음성 대화 관련 타입.
*   **`assets/`**: 이미지, 폰트, Live2D 모델 파일 등 정적 에셋.
*   **`App.css`, `index.css`**: 전역 및 기본 스타일.

### 백엔드 구조 (`BackEnd/app/`)

*   **`main.py`**: FastAPI 애플리케이션 진입점, 미들웨어 설정, 라우터 등록, 시작 이벤트 처리.
*   **`routers/`**: API 엔드포인트 정의.
    *   `voice_chat_router.py`: `/ws/voice_chat` 경로의 웹소켓 기반 실시간 음성 채팅 API.
    *   `__init__.py`: `api_router`를 구성하여 `main.py`에서 포함.
*   **`services/`**: 비즈니스 로직 구현.
    *   `stt_service.py`: Google STT를 이용한 음성-텍스트 변환 서비스.
    *   `tts_service.py`: Google TTS를 이용한 텍스트-음성 변환 서비스.
    *   `llm_service.py`: Google Generative AI (Gemini)를 이용한 질의응답 생성 서비스.
    *   `llm_emotion_service.py`: LLM을 이용한 감정 분석 서비스.
    *   `rag_service/`: RAG 파이프라인 관련 모듈.
        *   `__init__.py`: RAG 서비스 초기화 및 핵심 로직.
        *   `vector_store.py`: ChromaDB 벡터 저장소 관리.
        *   `embeddings.py`: 텍스트 임베딩 생성.
        *   `prompt_builder.py`: LLM에 전달할 프롬프트 생성.
    *   `session_manager.py`: 사용자 세션 관리 (웹소켓 연결 등).
*   **`core/`**: 핵심 설정 및 구성 요소.
    *   `config.py`: Pydantic을 사용한 환경 변수 및 애플리케이션 설정 관리.
*   **`utils/`**: 유틸리티 함수 및 클래스.
    *   `pipeline_manager.py`: 음성 처리 파이프라인(STT, LLM, TTS 등) 관리.
    *   `text_processor.py`: 텍스트 전처리/후처리 유틸리티.
    *   `websocket_utils.py`: 웹소켓 메시지 형식화 등 유틸리티.
*   **`data/`**:
    *   `vector_db/`: ChromaDB 데이터가 저장되는 디렉토리.

## 주요 기능

*   **실시간 양방향 음성 대화**:
    *   프론트엔드에서 마이크를 통해 사용자 음성 입력.
    *   백엔드에서 웹소켓을 통해 실시간 오디오 스트림 수신.
    *   Google STT를 이용한 빠른 음성 인식.
    *   LLM(Gemini)과 RAG를 결합하여 사용자의 질문에 대한 지능적인 답변 생성.
    *   생성된 답변을 Google TTS를 통해 자연스러운 음성으로 변환하여 프론트엔드로 스트리밍.
*   **Live2D 아바타 연동**:
    *   프론트엔드에서 PixiJS 및 `pixi-live2d-display`를 사용하여 Live2D 아바타 렌더링.
    *   AI의 답변 내용이나 분석된 감정(`emotions.ts` 참고)에 따라 아바타의 표정이나 모션 변화 (구현 예정 또는 진행 중).
*   **AI 기반 감정 분석**:
    *   백엔드 `llm_emotion_service.py`를 통해 사용자의 발화나 대화 맥락에서 감정 분석.
    *   분석된 감정 정보를 프론트엔드로 전달하여 아바타 표현 등에 활용.
*   **RAG (Retrieval Augmented Generation)**:
    *   `BackEnd/app/data/vector_db`에 구축된 벡터 저장소(ChromaDB)를 활용.
    *   사용자 질문과 관련된 문서를 검색하여 LLM 답변 생성의 정확도와 정보성을 향상.
*   **프론트엔드 UI/UX**:
    *   대화 내용(Transcript) 표시.
    *   마이크 상태, AI 발화 상태, 처리 시간 등 시각적 피드백 제공.
    *   오디오 컨텍스트(`AudioContext.tsx`)를 통한 오디오 장치 및 처리 관리.
*   **백엔드 핵심 로직**:
    *   음성 처리 파이프라인 (`pipeline_manager.py`): STT -> LLM (RAG 포함) -> 감정분석 -> TTS 순차 처리.
    *   세션 관리 (`session_manager.py`): 다중 사용자 환경을 위한 웹소켓 세션 관리.

## 설치 및 실행

### 사전 요구사항

*   **공통**: Git
*   **프론트엔드**: Node.js (npm 포함, 버전은 `package.json`의 `engines` 필드 또는 최신 LTS 권장)
*   **백엔드**: Python 3.12, pip
*   **백엔드 (선택적, Docker 실행 시)**: Docker Desktop 또는 Docker Engine
*   **Google Cloud Platform (GCP)**:
    *   GCP 프로젝트 생성 및 결제 계정 연결.
    *   필수 API 활성화:
        *   Speech-to-Text API
        *   Text-to-Speech API
        *   Vertex AI API (Gemini 모델 사용 시) 또는 Generative Language API
    *   서비스 계정 생성 및 키 파일 (JSON) 다운로드.
    *   `GOOGLE_APPLICATION_CREDENTIALS` 환경 변수에 다운로드한 JSON 키 파일 경로 설정.

### 프론트엔드 설정 (`FrontEnd/infoBank_Front/`)

1.  **저장소 클론**:
    ```bash
    git clone <저장소_URL>
    cd <저장소_경로>/FrontEnd/infoBank_Front
    ```
2.  **의존성 설치**:
    ```bash
    npm install
    ```
3.  **환경 변수 설정**:
    `.env.local` 파일을 프로젝트 루트에 생성하고 필요한 환경 변수를 설정합니다. (`src/constants/env.ts` 참고)
    ```env
    VITE_APP_WS_URL=ws://localhost:8000/ws/voice_chat # 백엔드 웹소켓 주소
    # 기타 필요한 환경 변수
    ```
4.  **개발 서버 실행**:
    ```bash
    npm run dev
    ```
    애플리케이션은 `http://localhost:5173` (Vite 기본 포트) 또는 `package.json`에 지정된 포트에서 실행됩니다.

5.  **프로덕션 빌드**:
    ```bash
    npm run build
    ```
    빌드 결과물은 `dist` 폴더에 생성됩니다.

### 백엔드 설정 (`BackEnd/`)

#### 로컬 개발 환경 (Python 가상 환경 권장)

1.  **저장소 클론 및 디렉토리 이동**:
    ```bash
    # 이미 클론했다면 생략
    cd <저장소_경로>/BackEnd
    ```
2.  **가상 환경 생성 및 활성화**:
    ```bash
    python -m venv venv
    source venv/bin/activate  # Linux/macOS
    # venv\Scripts\activate  # Windows
    ```
3.  **의존성 설치**:
    ```bash
    pip install -r requirements.txt
    ```
4.  **환경 변수 설정**:
    `BackEnd` 루트 디렉토리에 `.env` 파일을 생성하고 `app/core/config.py` 에 정의된 설정 값들을 입력합니다.
    ```env
    # GCP 설정
    GOOGLE_CLOUD_PROJECT_ID="your-gcp-project-id"
    # GOOGLE_APPLICATION_CREDENTIALS="/path/to/your/gcp-credentials.json" # 시스템 환경 변수로 설정 권장

    # 서버 설정
    SERVER_HOST="0.0.0.0"
    SERVER_PORT=8000
    ENVIRONMENT="development" # "production" 또는 "development"

    # CORS 설정 (개발 시에는 프론트엔드 주소 허용)
    ALLOWED_ORIGINS='["http://localhost:5173", "http://127.0.0.1:5173"]' # JSON 배열 형식의 문자열

    # LLM 설정
    GEMINI_MODEL_NAME="gemini-1.5-flash-latest" # 예시, 실제 사용하는 모델명으로 변경
    # VERTEX_AI_REGION="your-vertex-ai-region" # Vertex AI 사용 시

    # TTS/STT 상세 설정 (필요시 config.py에 추가 후 설정)
    # TTS_LANGUAGE_CODE="ko-KR"
    # TTS_VOICE_NAME="ko-KR-Wavenet-D"
    # STT_LANGUAGE_CODE="ko-KR"

    # RAG 서비스 설정
    CHROMA_DB_PATH="./app/data/vector_db"
    EMBEDDING_MODEL_NAME="text-embedding-004" # Google 임베딩 모델

    # 기타 API 키 (필요시)
    ```
    **중요**: `GOOGLE_APPLICATION_CREDENTIALS`는 시스템 환경 변수로 설정하는 것이 더 안전하고 일반적입니다.

5.  **(최초 실행 시) RAG 벡터 저장소 초기화**:
    백엔드 애플리케이션 실행 시 `rag_service.initialize()`가 호출되어 벡터 저장소를 로드하거나 생성합니다. 데이터 소스(예: 문서 파일)가 있다면 `rag_service` 관련 스크립트를 실행하여 임베딩 및 저장을 먼저 수행해야 할 수 있습니다. (관련 스크립트는 `scripts/` 폴더에 있을 수 있으며, 현재는 내용 미확인)

6.  **개발 서버 실행 (Uvicorn)**:
    ```bash
    uvicorn app.main:app --host 0.0.0.0 --port 8000 --reload
    ```
    API 서버는 `http://localhost:8000` 에서 실행됩니다.

#### Docker 환경

1.  **저장소 클론 및 디렉토리 이동**:
    ```bash
    # 이미 클론했다면 생략
    cd <저장소_경로>/BackEnd
    ```
2.  **환경 변수 파일 준비**:
    위에서 설명한 `.env` 파일을 `BackEnd` 루트에 준비합니다. Docker 실행 시 이 파일을 참조합니다.

3.  **Docker 이미지 빌드**:
    ```bash
    docker build -t infobank-backend .
    ```
4.  **Docker 컨테이너 실행**:
    ```bash
    docker run -d -p 8080:8080 --env-file .env -v /path/to/your/gcp-credentials.json:/app/gcp-credentials.json -e GOOGLE_APPLICATION_CREDENTIALS="/app/gcp-credentials.json" infobank-backend
    ```
    *   `-p 8080:8080`: 호스트의 8080 포트를 컨테이너의 8080 포트(Dockerfile에서 노출 및 CMD에서 사용)로 매핑합니다.
    *   `--env-file .env`: `.env` 파일의 환경 변수를 컨테이너에 주입합니다.
    *   `-v /path/to/your/gcp-credentials.json:/app/gcp-credentials.json`: GCP 서비스 계정 키 파일을 컨테이너 내부로 마운트합니다.
    *   `-e GOOGLE_APPLICATION_CREDENTIALS="/app/gcp-credentials.json"`: 컨테이너 내의 키 파일 경로를 환경 변수로 설정합니다.
    애플리케이션은 `http://localhost:8080` 에서 실행됩니다.

## 사용 방법

1.  위 "설치 및 실행" 가이드에 따라 백엔드 서버를 실행합니다. (로컬 또는 Docker)
2.  프론트엔드 개발 서버를 실행합니다.
3.  웹 브라우저에서 프론트엔드 주소(기본: `http://localhost:5173`)로 접속합니다.
4.  페이지가 로드되면 Live2D 아바타와 함께 음성 채팅 인터페이스가 나타납니다.
5.  마이크 사용 권한을 요청하면 허용합니다.
6.  화면의 컨트롤 버튼(예: 마이크 버튼)을 사용하여 음성 입력을 시작/종료합니다.
7.  AI 어시스턴트에게 자유롭게 질문하거나 대화를 시도합니다.
8.  AI의 음성 답변과 함께 대화 내용이 화면에 표시되며, Live2D 아바타가 반응하는 것을 관찰할 수 있습니다. (감정 표현 연동 시)

![메인 화면 스크린샷](./screenshots/chat_example.gif)

## API 엔드포인트 (백엔드)

백엔드는 FastAPI를 사용하여 구현되었으며, 주요 엔드포인트는 다음과 같습니다:

*   **`GET /`**: API 서버 상태 및 환영 메시지를 반환합니다.
*   **`WebSocket /ws/voice_chat`**:
    *   실시간 음성 채팅을 위한 웹소켓 연결 엔드포인트입니다.
    *   클라이언트(프론트엔드)로부터 오디오 스트림 및 제어 메시지를 수신합니다.
    *   서버로부터 STT 결과, LLM 답변, TTS 오디오 스트림, 감정 분석 결과 등을 클라이언트로 전송합니다.
    *   세부 프로토콜은 `app/routers/voice_chat_router.py` 및 프론트엔드의 `src/utils/webSocketUtils.ts`, `src/hooks/useVoiceConversation.tsx`를 참고하십시오.
*   **(존재한다면) 기타 RESTful API 엔드포인트**: `app/routers/__init__.py` 및 해당 파일에 포함된 다른 라우터 파일들을 참고하십시오. 현재는 `voice_chat_router` 외의 명시적인 HTTP API 라우터는 확인되지 않았습니다.
