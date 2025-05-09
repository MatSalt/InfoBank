/**
 * 로그 레벨을 정의하는 열거형
 */
export enum LogLevel {
  ERROR = 0,   // 오류만 표시
  WARN = 1,    // 경고 및 오류 표시
  INFO = 2,    // 정보, 경고, 오류 표시
  DEBUG = 3,   // 디버그, 정보, 경고, 오류 표시
  VERBOSE = 4, // 모든 로그 표시
}

/**
 * 현재 환경에 따라 로그 레벨 설정
 * - 개발환경: 모든 로그 표시
 * - 프로덕션: 정보, 경고, 오류만 표시
 */
const IS_PRODUCTION = import.meta.env.PROD === true;

// 프로덕션 환경이면 INFO 레벨, 그렇지 않으면 VERBOSE 레벨
export const LOG_LEVEL = IS_PRODUCTION ? LogLevel.INFO : LogLevel.VERBOSE;

/**
 * 로그를 출력하는 유틸리티 클래스
 */
export class Logger {
  private context: string;

  /**
   * 로거 생성
   * @param context 로그 컨텍스트 (일반적으로 컴포넌트나 파일 이름)
   */
  constructor(context: string) {
    this.context = context;
  }

  /**
   * 오류 로그 출력 (항상 표시)
   */
  error(message: string, ...args: unknown[]): void {
    if (LOG_LEVEL >= LogLevel.ERROR) {
      console.error(`[${this.context}] ${message}`, ...args);
    }
  }

  /**
   * 경고 로그 출력
   */
  warn(message: string, ...args: unknown[]): void {
    if (LOG_LEVEL >= LogLevel.WARN) {
      console.warn(`[${this.context}] ${message}`, ...args);
    }
  }

  /**
   * 정보 로그 출력
   */
  info(message: string, ...args: unknown[]): void {
    if (LOG_LEVEL >= LogLevel.INFO) {
      console.info(`[${this.context}] ${message}`, ...args);
    }
  }

  /**
   * 디버그 로그 출력 (개발 환경에서만 표시)
   */
  debug(message: string, ...args: unknown[]): void {
    if (LOG_LEVEL >= LogLevel.DEBUG) {
      console.log(`[${this.context}:debug] ${message}`, ...args);
    }
  }

  /**
   * 상세 로그 출력 (개발 환경에서만 표시)
   */
  verbose(message: string, ...args: unknown[]): void {
    if (LOG_LEVEL >= LogLevel.VERBOSE) {
      console.log(`[${this.context}:verbose] ${message}`, ...args);
    }
  }
}

/**
 * 로거 인스턴스를 생성하는 팩토리 함수
 * @param context 로그 컨텍스트 (일반적으로 컴포넌트나 파일 이름)
 */
export const createLogger = (context: string): Logger => {
  return new Logger(context);
}; 