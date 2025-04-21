# 1. 베이스 이미지 선택 (Python 3.12 슬림 버전 사용, linux/amd64 플랫폼 지정)
FROM python:3.12-slim

# 2. 작업 디렉토리 설정
WORKDIR /app

# 3. 환경 변수 설정 (Cloud Run이 포트 8080을 기본으로 사용)
# main.py에서 PORT 환경 변수를 읽으므로 여기서 설정합니다.
ENV PORT=8080
# Python이 .pyc 파일을 만들지 않도록 설정 (선택 사항)
ENV PYTHONDONTWRITEBYTECODE=1
# Python 출력 버퍼링 비활성화 (로그 확인 용이)
ENV PYTHONUNBUFFERED=1

# 4. 의존성 파일 복사 및 설치
# requirements.txt만 먼저 복사하여 Docker 빌드 캐시를 활용합니다.
COPY requirements.txt requirements.txt
RUN pip install --no-cache-dir --upgrade pip && \
    pip install --no-cache-dir -r requirements.txt

# 5. 프로젝트 소스 코드 전체 복사
COPY . .

# 6. 컨테이너가 리스닝할 포트 지정 (문서화 목적 및 로컬 테스트 시 사용)
EXPOSE 8080

# 7. 애플리케이션 실행 명령어
# Cloud Run 환경에서는 uvicorn을 직접 실행합니다.
# main.py의 if __name__ == "__main__": 블록은 사용되지 않습니다.
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8080"] 