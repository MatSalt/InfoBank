#!/usr/bin/env python3
"""
CORS 설정 검사 스크립트

이 스크립트는 환경 변수 또는 .env 파일에서 CORS 설정을 확인하고
보안 권장사항에 따라 문제가 있는지 알려줍니다.
"""

import os
import sys
from dotenv import load_dotenv
import argparse

def print_colored(text, color_code):
    """색상이 있는 텍스트 출력"""
    print(f"\033[{color_code}m{text}\033[0m")

def print_error(text):
    """빨간색 오류 메시지"""
    print_colored(text, "31")

def print_warning(text):
    """노란색 경고 메시지"""
    print_colored(text, "33")

def print_success(text):
    """녹색 성공 메시지"""
    print_colored(text, "32")

def print_info(text):
    """파란색 정보 메시지"""
    print_colored(text, "36")

def check_cors_settings():
    """CORS 설정 검사"""
    # .env 파일 로드
    load_dotenv()
    
    # 환경 확인
    environment = os.getenv("ENVIRONMENT", "development").lower()
    print_info(f"실행 환경: {environment}")
    
    # CORS 설정 확인
    allowed_origins = os.getenv("ALLOWED_ORIGINS", "")
    origins_list = allowed_origins.split(",") if allowed_origins else []
    
    print_info(f"설정된 CORS 허용 출처: {allowed_origins}")
    
    has_issues = False
    
    # 와일드카드 검사
    if "*" in origins_list:
        if environment == "production":
            print_error("[심각] 프로덕션 환경에서 모든 오리진(*)을 허용하는 CORS 설정이 감지되었습니다.")
            print_error("이는 보안 취약점으로, 특정 도메인만 허용하도록 설정하세요.")
            has_issues = True
        else:
            print_warning("[경고] 개발 환경에서 모든 오리진(*)을 허용하는 CORS 설정이 감지되었습니다.")
            print_warning("개발 환경에서는 허용되지만, 프로덕션 환경에서는 사용하지 마세요.")
    
    # 빈 설정 검사
    if not origins_list:
        print_error("[오류] ALLOWED_ORIGINS 환경 변수가 설정되지 않았습니다.")
        has_issues = True
    
    # 도메인 유효성 검사
    invalid_domains = []
    for origin in origins_list:
        if origin == "*":
            continue
        if not (origin.startswith("http://") or origin.startswith("https://")):
            invalid_domains.append(origin)
    
    if invalid_domains:
        print_error(f"[오류] 다음 도메인은 올바른 형식이 아닙니다: {', '.join(invalid_domains)}")
        print_info("모든 도메인은 'http://' 또는 'https://'로 시작해야 합니다.")
        has_issues = True
    
    # HTTP 사용 검사 (프로덕션 환경)
    if environment == "production":
        http_domains = [origin for origin in origins_list if origin.startswith("http://") and "localhost" not in origin and "127.0.0.1" not in origin]
        if http_domains:
            print_warning(f"[경고] 프로덕션 환경에서 안전하지 않은 HTTP 도메인이 감지되었습니다: {', '.join(http_domains)}")
            print_warning("프로덕션 환경에서는 HTTPS를 사용하는 것이 좋습니다.")
            has_issues = True
    
    if not has_issues:
        print_success("[✅] CORS 설정이 보안 권장사항을 준수합니다.")
    
    return not has_issues

def main():
    """메인 함수"""
    parser = argparse.ArgumentParser(description="CORS 설정 검사 도구")
    parser.add_argument("--env", help=".env 파일 경로 (기본값: 현재 디렉토리의 .env 파일)", default=".env")
    args = parser.parse_args()
    
    # 지정된 .env 파일 확인
    if args.env != ".env" and os.path.exists(args.env):
        load_dotenv(args.env)
        print_info(f"{args.env} 파일에서 환경 변수를 로드했습니다.")
    
    print_info("CORS 설정 검사 중...")
    success = check_cors_settings()
    
    print("\n권장 설정:")
    print_info("개발 환경: ALLOWED_ORIGINS=http://localhost:5173,http://localhost:3000,http://127.0.0.1:5173")
    print_info("프로덕션 환경: ALLOWED_ORIGINS=https://yourdomain.com,https://admin.yourdomain.com")
    
    if not success:
        sys.exit(1)

if __name__ == "__main__":
    main() 