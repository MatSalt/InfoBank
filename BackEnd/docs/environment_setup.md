# 환경 변수 설정 가이드

이 문서는 InfoBank 백엔드 서버를 위한 환경 변수 설정 방법을 설명합니다.

## 필수 환경 변수

다음 환경 변수들은 **반드시** 설정해야 합니다:

| 환경 변수 | 설명 | 예시 |
|------------|-------------|---------|
| `GOOGLE_CLOUD_PROJECT_ID` | Google Cloud 프로젝트 ID | `your-project-id` |
| `VERTEX_AI_LOCATION` | Vertex AI 서비스 리전 | `asia-northeast3` |
| `TTS_VOICE_NAME` | TTS 음성 이름 | `ko-KR-Standard-A` |
| `TTS_LANGUAGE_CODE` | TTS 언어 코드 | `ko-KR` |

## 선택적 환경 변수

다음 환경 변수들은 기본값이 있으므로 필요에 따라 변경할 수 있습니다:

| 환경 변수 | 설명 | 기본값 |
|------------|-------------|---------|
| `SERVER_HOST` | 서버 호스트 주소 | `0.0.0.0` |
| `PORT` | 서버 포트 | `8080` |
| `ALLOWED_ORIGINS` | CORS 허용 출처 | 개발환경 도메인 목록 |
| `ENVIRONMENT` | 실행 환경 (development/production) | `development` |
| `STT_SAMPLE_RATE` | 오디오 샘플링 레이트 | `16000` |
| `STT_LANGUAGE_CODES` | 인식할 언어 코드 목록 | `en-US,ko-KR` |
| `STT_MODEL` | STT 모델 | `telephony` |
| `GEMINI_MODEL` | Gemini 모델 | `gemini-1.5-flash-002` |
| `USE_VERTEX_AI` | Vertex AI 사용 여부 | `True` |

## CORS 설정 가이드

### ALLOWED_ORIGINS 환경 변수

이 환경 변수는 Cross-Origin Resource Sharing(CORS) 보안 정책을 설정하는 데 사용됩니다. 서버에 접근할 수 있는 도메인을 제어하여 웹 애플리케이션의 보안을 강화합니다.

#### 개발 환경

개발 환경에서는 기본적으로 다음 도메인이 허용됩니다:
- `http://localhost:5173` (Vite 개발 서버)
- `http://localhost:3000`
- `http://127.0.0.1:5173`
- `http://127.0.0.1:3000`

#### 프로덕션 환경

**프로덕션 환경에서는 반드시 명시적인 도메인 목록을 지정해야 합니다.** 와일드카드(`*`)를 사용하면 보안 취약점이 발생할 수 있습니다.

```
# 올바른 설정 예시 (프로덕션)
ALLOWED_ORIGINS=https://yourdomain.com,https://api.yourdomain.com,https://admin.yourdomain.com
```

#### 여러 도메인 지정 방법

쉼표(,)로 구분된 도메인 목록을 사용합니다:

```
ALLOWED_ORIGINS=https://domain1.com,https://domain2.com,https://domain3.com
```

#### 보안 위험

모든 도메인을 허용하는 `*` 설정은 다음과 같은 보안 위험이 있습니다:
- 크로스 사이트 요청 위조(CSRF) 공격 취약성 증가
- 악의적인 사이트에서 API에 액세스할 가능성
- 데이터 유출 위험

## 환경 변수 설정 방법

### 1. .env 파일 사용

프로젝트 루트 디렉토리에 `.env` 파일을 생성하여 환경 변수를 설정할 수 있습니다:

```
# 필수 환경 변수
GOOGLE_CLOUD_PROJECT_ID=your-project-id
VERTEX_AI_LOCATION=asia-northeast3
TTS_VOICE_NAME=ko-KR-Standard-A
TTS_LANGUAGE_CODE=ko-KR

# 선택적 환경 변수
SERVER_HOST=0.0.0.0
PORT=8080

# 환경 설정
ENVIRONMENT=development

# CORS 설정 (개발 환경)
ALLOWED_ORIGINS=http://localhost:5173,http://localhost:3000

# CORS 설정 (프로덕션 환경)
# ALLOWED_ORIGINS=https://yourdomain.com,https://admin.yourdomain.com
```

### 2. 시스템 환경 변수 사용

시스템 환경 변수로 설정할 수도 있습니다:

```bash
# Linux/Mac
export GOOGLE_CLOUD_PROJECT_ID=your-project-id
export VERTEX_AI_LOCATION=asia-northeast3
export ALLOWED_ORIGINS=https://yourdomain.com,https://admin.yourdomain.com
export ENVIRONMENT=production

# Windows
set GOOGLE_CLOUD_PROJECT_ID=your-project-id
set VERTEX_AI_LOCATION=asia-northeast3
set ALLOWED_ORIGINS=https://yourdomain.com,https://admin.yourdomain.com
set ENVIRONMENT=production
```

### 3. Docker 환경 변수 사용

Docker를 사용하는 경우 다음과 같이 환경 변수를 전달할 수 있습니다:

```bash
docker run \
  -e GOOGLE_CLOUD_PROJECT_ID=your-project-id \
  -e VERTEX_AI_LOCATION=asia-northeast3 \
  -e ALLOWED_ORIGINS=https://yourdomain.com,https://admin.yourdomain.com \
  -e ENVIRONMENT=production \
  -p 8080:8080 infobank-api
```

## 보안 고려사항

- 프로덕션 환경에서는 하드코딩된 값을 사용하지 마세요.
- 민감한 키나 자격 증명은 항상 환경 변수나 안전한 시크릿 관리 시스템을 통해 관리하세요.
- `.env` 파일은 버전 관리 시스템에 포함시키지 마세요 (`.gitignore`에 추가).
- 프로덕션 환경에서는 `ALLOWED_ORIGINS`를 구체적인 도메인으로 제한하세요. 