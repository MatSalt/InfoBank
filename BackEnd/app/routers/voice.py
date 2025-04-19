# backend/app/routers/voice.py
import logging
import asyncio
from fastapi import APIRouter, WebSocket, WebSocketDisconnect
from app.services.stt_service import handle_stt_stream # STT 서비스 함수 임포트
from app.services.llm_service import stream_llm_response # LLM 서비스 함수 임포트

# 로거 설정 (main.py에서 설정된 로거 사용 또는 여기서 별도 설정 가능)
logger = logging.getLogger(__name__)

# APIRouter 인스턴스 생성
router = APIRouter(
    prefix="/ws", # 이 라우터의 모든 경로 앞에 /ws 접두사 추가
    tags=["voice"], # API 문서에서 태그별로 그룹화
)

@router.websocket("/audio")
async def websocket_endpoint(websocket: WebSocket):
    """
    WebSocket 연결을 처리하고, 오디오를 수신하여 STT 서비스로 전달하고,
    최종 STT 결과를 LLM 서비스로 전달하여 응답을 터미널에 스트리밍합니다.
    """
    await websocket.accept() # 클라이언트의 웹소켓 연결 요청 수락
    client_host = websocket.client.host
    client_port = websocket.client.port
    client_info = f"{client_host}:{client_port}"
    logger.info(f"WebSocket 연결 수락됨: {client_info}")

    audio_queue = asyncio.Queue() # 오디오 청크를 담을 비동기 큐
    stt_task = None # STT 처리 태스크
    llm_tasks = set() # LLM 처리 태스크 집합 (여러 개 동시 실행 가능성 고려)

    # --- STT 결과 처리 콜백 함수 ---
    async def process_stt_result(transcript: str, is_final: bool):
        """STT 결과를 로그로 남기고, 최종 결과는 LLM 서비스로 전달하는 콜백 함수"""
        nonlocal llm_tasks # 외부 함수의 llm_tasks 변수 사용 명시

        if not is_final:
            logger.debug(f"[{client_info}] 중간 결과: {transcript}")
            # 필요시 중간 결과를 클라이언트에게 전송할 수 있음
            # await websocket.send_text(f"중간 인식: {transcript}")
        else:
            logger.info(f"[{client_info}] 최종 결과: {transcript}")
            if transcript.strip(): # 빈 문자열이 아닌 경우에만 LLM 호출
                logger.info(f"[{client_info}] 최종 결과로 LLM 서비스 호출 시작...")
                # LLM 호출을 별도의 태스크로 실행하여 WebSocket 핸들러를 블록하지 않음
                llm_task = asyncio.create_task(
                    stream_llm_response(transcript, client_info)
                )
                llm_tasks.add(llm_task) # 태스크 집합에 추가
                # 태스크 완료 시 집합에서 제거하는 콜백 추가
                llm_task.add_done_callback(llm_tasks.discard)
                logger.debug(f"[{client_info}] LLM 서비스 태스크 생성됨: {llm_task.get_name()}")
            else:
                logger.info(f"[{client_info}] 최종 결과가 비어있어 LLM을 호출하지 않음.")
            # 최종 결과를 클라이언트에게 전송할 수도 있음
            # await websocket.send_text(f"최종 인식: {transcript}")

    try:
        # --- STT 서비스 시작 ---
        stt_task = asyncio.create_task(
            handle_stt_stream(audio_queue, process_stt_result)
        )
        logger.info(f"[{client_info}] STT 서비스 태스크 시작됨.")

        # --- 클라이언트로부터 오디오 수신 ---
        while True:
            data = await websocket.receive() # 클라이언트로부터 메시지 수신 대기

            if "bytes" in data: # 수신된 데이터가 오디오 청크(bytes)인 경우
                audio_chunk = data["bytes"]
                if audio_chunk: # 빈 청크가 아닌 경우에만 큐에 추가
                    logger.debug(f"[{client_info}] 오디오 청크 수신: {len(audio_chunk)} bytes")
                    await audio_queue.put(audio_chunk)
                    logger.debug(f"[{client_info}] 오디오 청크를 큐에 추가 완료.")
                else:
                     logger.debug(f"[{client_info}] 빈 오디오 청크 수신, 무시함.")

            elif "text" in data: # 수신된 데이터가 텍스트인 경우
                text_data = data["text"]
                logger.info(f"텍스트 메시지 수신: {text_data} from {client_info}")
                # 클라이언트가 녹음 중지 또는 연결 종료 신호를 보낸 경우 처리
                if text_data == "Client stopped recording" or text_data == "disconnect":
                    logger.info(f"클라이언트 {client_info}가 중지 신호 보냄. 스트림 종료 중.")
                    break # 오디오 수신 루프 종료

    except WebSocketDisconnect as e: # 웹소켓 연결이 끊어진 경우
        logger.warning(f"WebSocket 연결 끊김: {client_info} - 코드: {e.code}, 이유: {e.reason}")
    except Exception as e: # 그 외 예외 발생 시
        logger.error(f"WebSocket 연결 중 오류 발생 ({client_info}): {e}", exc_info=True)
        try:
            await websocket.close(code=1011, reason=f"Server error: {e}")
        except Exception:
            pass # 이미 닫혔을 수 있음
    finally: # 연결 종료 또는 예외 발생 시 항상 실행
        logger.info(f"[{client_info}] WebSocket 연결 정리 중...")

        # STT 서비스에게 오디오 전송 중단 신호 보내기
        if audio_queue:
             logger.debug(f"[{client_info}] 오디오 큐에 종료 신호(None) 전송 중...")
             await audio_queue.put(None) # 제너레이터를 중지시키기 위한 None 값(Sentinel) 전송
             logger.debug(f"[{client_info}] 오디오 큐에 종료 신호 전송 완료.")

        # STT 처리 태스크 취소 및 대기
        if stt_task and not stt_task.done():
            logger.info(f"[{client_info}] STT 서비스 태스크 취소 시도...")
            stt_task.cancel() # 태스크 취소 요청
            try:
                await stt_task # 태스크가 완전히 종료될 때까지 대기
            except asyncio.CancelledError:
                logger.info(f"[{client_info}] STT 서비스 태스크 성공적으로 취소됨.")
            except Exception as e:
                 logger.error(f"[{client_info}] STT 태스크 종료 대기 중 오류 발생: {e}", exc_info=True)
        else:
             logger.info(f"[{client_info}] STT 태스크가 이미 완료되었거나 존재하지 않음.")


        # 실행 중인 모든 LLM 태스크 취소 및 대기
        if llm_tasks:
            logger.info(f"[{client_info}] 실행 중인 LLM 태스크 {len(llm_tasks)}개 취소 시도...")
            # Create a list of tasks to await to avoid modifying the set during iteration
            tasks_to_await = list(llm_tasks)
            for task in tasks_to_await:
                if not task.done():
                    task.cancel()
            # Wait for all cancelled tasks
            results = await asyncio.gather(*tasks_to_await, return_exceptions=True)
            for i, result in enumerate(results):
                task_name = tasks_to_await[i].get_name() if hasattr(tasks_to_await[i], 'get_name') else f"Task-{i}"
                if isinstance(result, asyncio.CancelledError):
                    logger.info(f"[{client_info}] LLM 태스크 {task_name} 성공적으로 취소됨.")
                elif isinstance(result, Exception):
                    logger.error(f"[{client_info}] LLM 태스크 {task_name} 종료 중 오류 발생: {result}", exc_info=result)
                else:
                     logger.info(f"[{client_info}] LLM 태스크 {task_name} 정상 종료됨.")
        else:
            logger.info(f"[{client_info}] 실행 중인 LLM 태스크 없음.")


        # 웹소켓이 아직 닫히지 않았다면 닫기 시도
        try:
            # Check state before closing
             if websocket.application_state == websocket.application_state.CONNECTED:
                 await websocket.close()
                 logger.info(f"[{client_info}] WebSocket 연결 명시적으로 닫힘.")
             else:
                 logger.info(f"[{client_info}] WebSocket 연결이 이미 닫힌 상태({websocket.application_state}).")

        except Exception as e:
            logger.warning(f"[{client_info}] WebSocket 닫기 오류 (이미 닫혔을 수 있음): {e}")

        logger.info(f"WebSocket 연결 종료됨: {client_info}")
