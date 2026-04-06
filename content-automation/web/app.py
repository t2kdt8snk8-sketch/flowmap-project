from __future__ import annotations

import asyncio
import json
import uuid
from pathlib import Path
from typing import Any

from fastapi import FastAPI, Request, Response, WebSocket, WebSocketDisconnect
from fastapi.responses import HTMLResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from loguru import logger
from pydantic import BaseModel

from core.models import TaskRequest
from core.orchestrator import run_workflow
from storage.output_store import save_result
from web.auth import create_token, revoke_token, verify_password, verify_token

app = FastAPI(title="Content Automation")

_STATIC_DIR = Path(__file__).parent / "static"
app.mount("/static", StaticFiles(directory=str(_STATIC_DIR)), name="static")


# ── 인증 ──────────────────────────────────────────────────────────────────────

class LoginRequest(BaseModel):
    password: str


@app.post("/api/login")
async def login(body: LoginRequest, response: Response) -> JSONResponse:
    if not verify_password(body.password):
        return JSONResponse({"error": "비밀번호가 틀렸어요"}, status_code=401)
    token = create_token()
    response.set_cookie("token", token, httponly=True, samesite="lax", max_age=86400 * 7)
    return JSONResponse({"token": token})


@app.post("/api/logout")
async def logout(request: Request, response: Response) -> JSONResponse:
    token = request.cookies.get("token")
    if token:
        revoke_token(token)
    response.delete_cookie("token")
    return JSONResponse({"ok": True})


@app.get("/api/me")
async def me(request: Request) -> JSONResponse:
    token = _extract_token(request)
    if not verify_token(token):
        return JSONResponse({"authenticated": False}, status_code=401)
    return JSONResponse({"authenticated": True})


# ── WebSocket ─────────────────────────────────────────────────────────────────

@app.websocket("/ws")
async def websocket_endpoint(websocket: WebSocket) -> None:
    token = websocket.query_params.get("token") or websocket.cookies.get("token")
    if not verify_token(token):
        await websocket.close(code=4001, reason="Unauthorized")
        return

    await websocket.accept()
    logger.info(f"WebSocket connected: {websocket.client}")

    approval_queue: asyncio.Queue[dict[str, Any]] = asyncio.Queue()
    workflow_task: asyncio.Task[Any] | None = None

    try:
        while True:
            raw = await websocket.receive_text()
            data: dict[str, Any] = json.loads(raw)
            msg_type = data.get("type")

            if msg_type == "run_workflow":
                # 이미 실행 중이면 무시
                if workflow_task and not workflow_task.done():
                    await _send(websocket, {
                        "type": "error",
                        "error": "이미 실행 중이에요. 완료 후 새 요청을 보내주세요.",
                    })
                    continue

                user_message = data.get("message", "").strip()
                if not user_message:
                    continue

                # approval_queue 초기화 (이전 잔여 메시지 제거)
                while not approval_queue.empty():
                    approval_queue.get_nowait()

                task_id = str(uuid.uuid4())
                request_obj = TaskRequest(
                    task_id=task_id,
                    user_message=user_message,
                    chat_id=f"web_{task_id[:8]}",
                )

                async def on_event(event: dict[str, Any]) -> None:
                    await _send(websocket, event)

                async def run_and_save() -> None:
                    try:
                        run = await run_workflow(
                            request_obj,
                            on_event=on_event,
                            approval_queue=approval_queue,
                        )
                        await save_result(run)
                    except Exception as e:
                        logger.error(f"Workflow error: {e}", exc_info=True)
                        await _send(websocket, {"type": "workflow_failed", "error": str(e)})

                workflow_task = asyncio.create_task(run_and_save())

            elif msg_type in ("approve", "feedback"):
                # 실행 중인 워크플로우에 사용자 액션 전달
                await approval_queue.put(data)

            elif msg_type == "cancel":
                if workflow_task and not workflow_task.done():
                    workflow_task.cancel()
                    await _send(websocket, {"type": "workflow_cancelled"})

    except WebSocketDisconnect:
        logger.info(f"WebSocket disconnected: {websocket.client}")
        if workflow_task and not workflow_task.done():
            workflow_task.cancel()
    except Exception as e:
        logger.error(f"WebSocket error: {e}", exc_info=True)


# ── SPA 진입점 ────────────────────────────────────────────────────────────────

@app.get("/", response_class=HTMLResponse)
async def root() -> HTMLResponse:
    html_path = _STATIC_DIR / "index.html"
    return HTMLResponse(html_path.read_text(encoding="utf-8"))


# ── 헬퍼 ──────────────────────────────────────────────────────────────────────

async def _send(ws: WebSocket, data: dict[str, Any]) -> None:
    try:
        await ws.send_text(json.dumps(data, ensure_ascii=False))
    except Exception:
        pass


def _extract_token(request: Request) -> str | None:
    auth = request.headers.get("Authorization", "")
    if auth.startswith("Bearer "):
        return auth[7:]
    return request.cookies.get("token")
