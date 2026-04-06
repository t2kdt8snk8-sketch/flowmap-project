from __future__ import annotations

import asyncio
import time
from collections.abc import Awaitable, Callable
from datetime import datetime
from typing import Any

import anthropic
from loguru import logger

from agents.registry import TOOL_DEFINITIONS, get_agent_callable
from core.llm_client import call_opus_with_tools
from core.models import AgentResult, TaskRequest, WorkflowRun

MAX_ITERATIONS = 10

_ORCHESTRATOR_SYSTEM = """\
You are a content automation orchestrator. Given a user's content request, use the \
available tools (agents) to fulfill it. Each tool represents a specialized agent.

Available agents:
- research_agent: web search and trend analysis — use first when fresh data is needed
- copy_agent: Korean/English copywriting and captions — use for any written content
- image_prompt_agent: Midjourney/Flux image prompts — use when visuals are needed
- script_agent: video/podcast script writing — use when video is the deliverable
- format_agent: formats final output as clean markdown — ALWAYS call this last

Strategy:
1. Analyze the request and decide which agents are needed (skip what isn't relevant)
2. Call agents in logical order: research → content creation → format
3. When calling later agents, pass relevant outputs from earlier agents in the 'context' field
4. Always call format_agent as your final step to produce a polished result
5. Once format_agent is done, respond with a brief summary of what was created

The user may inject feedback between agent steps. Incorporate any feedback into your \
next decisions and pass it in the context field to the relevant agents.

Be efficient: a caption-only request doesn't need image prompts or a script.\
"""


async def run_workflow(
    request: TaskRequest,
    on_event: Callable[[dict[str, Any]], Awaitable[None]] | None = None,
    approval_queue: asyncio.Queue[dict[str, Any]] | None = None,
) -> WorkflowRun:
    """Execute a content automation workflow.

    Args:
        request: The user's task.
        on_event: Optional async callback — called with progress events for the UI.
        approval_queue: Optional asyncio.Queue — when provided the workflow pauses
            at each step waiting for {"type": "approve"} or {"type": "feedback",
            "message": "..."}. When None (Telegram bot), runs fully automatically.
    """
    workflow_start = time.monotonic()
    run = WorkflowRun(
        task_id=request.task_id,
        request=request,
        status="running",
        started_at=datetime.utcnow(),
    )

    messages: list[dict[str, Any]] = [
        {"role": "user", "content": request.user_message}
    ]
    accumulated_context = ""

    logger.info(f"[{request.task_id}] Starting workflow: {request.user_message[:80]}")

    for iteration in range(MAX_ITERATIONS):
        logger.debug(f"[{request.task_id}] Orchestrator iteration {iteration + 1}")

        try:
            response = await call_opus_with_tools(
                system=_ORCHESTRATOR_SYSTEM,
                messages=messages,
                tools=TOOL_DEFINITIONS,
            )
        except Exception as e:
            logger.error(f"[{request.task_id}] Opus call failed: {e}")
            await _safe_emit(on_event, {"type": "workflow_failed", "error": str(e)})
            run.status = "failed"
            run.completed_at = datetime.utcnow()
            return run

        messages.append({"role": "assistant", "content": response.content})

        if response.stop_reason == "end_turn":
            for block in response.content:
                if isinstance(block, anthropic.types.TextBlock):
                    run.final_output = block.text
                    break
            total_ms = round((time.monotonic() - workflow_start) * 1000)
            await _safe_emit(on_event, {
                "type": "workflow_completed",
                "final_output": run.final_output,
                "total_ms": total_ms,
            })
            logger.info(f"[{request.task_id}] Workflow complete after {iteration + 1} iterations")
            break

        if response.stop_reason != "tool_use":
            logger.warning(f"[{request.task_id}] Unexpected stop_reason: {response.stop_reason}")
            break

        # ── 중단점 A: Opus가 실행할 에이전트 목록 결정 직후 ──────────────────
        planned = [
            b.name for b in response.content
            if isinstance(b, anthropic.types.ToolUseBlock)
        ]
        await _safe_emit(on_event, {"type": "plan_step", "agents": planned})

        if approval_queue is not None:
            user_action = await approval_queue.get()
            if user_action.get("type") == "feedback":
                # 피드백을 대화에 추가하고 Opus 재호출 (에이전트 실행 없이)
                feedback_msg = user_action.get("message", "")
                messages.append({"role": "user", "content": feedback_msg})
                logger.info(f"[{request.task_id}] Plan feedback: {feedback_msg[:60]}")
                continue
            # type == "approve" → 아래로 진행

        # ── 에이전트 실행 ─────────────────────────────────────────────────────
        tool_results: list[dict[str, Any]] = []

        for block in response.content:
            if not isinstance(block, anthropic.types.ToolUseBlock):
                continue

            agent_name = block.name
            tool_input: dict[str, Any] = dict(block.input)  # type: ignore[arg-type]

            if "context" in _get_tool_schema_properties(agent_name):
                tool_input.setdefault("context", accumulated_context)

            await _safe_emit(on_event, {
                "type": "agent_started",
                "agent": agent_name,
            })
            logger.info(f"[{request.task_id}] → {agent_name}({list(tool_input.keys())})")
            t0 = time.monotonic()

            try:
                agent_fn = get_agent_callable(agent_name)
                result: AgentResult = await agent_fn(request, tool_input)
                elapsed = (time.monotonic() - t0) * 1000
                logger.info(
                    f"[{request.task_id}] ← {agent_name} "
                    f"({'ok' if result.success else 'err'}) {elapsed:.0f}ms"
                )
                run.agent_results.append(result)

                if result.success:
                    accumulated_context += f"\n\n--- {agent_name} output ---\n{result.content}"

                # ── 중단점 B: 에이전트 완료 직후 ─────────────────────────────
                await _safe_emit(on_event, {
                    "type": "agent_completed",
                    "agent": agent_name,
                    "content": result.content if result.success else None,
                    "error": result.error if not result.success else None,
                    "elapsed_ms": round(elapsed),
                })

                if approval_queue is not None:
                    user_action = await approval_queue.get()
                    if user_action.get("type") == "feedback":
                        feedback_msg = user_action.get("message", "")
                        accumulated_context += (
                            f"\n\nUser feedback on {agent_name}: {feedback_msg}"
                        )
                        logger.info(
                            f"[{request.task_id}] Agent feedback ({agent_name}): "
                            f"{feedback_msg[:60]}"
                        )
                    # approve 또는 feedback 모두 다음 에이전트로 진행

                tool_results.append({
                    "type": "tool_result",
                    "tool_use_id": block.id,
                    "content": result.content if result.success
                               else f"ERROR: {result.error}",
                })

            except Exception as e:
                logger.error(f"[{request.task_id}] Agent {agent_name} raised: {e}")
                await _safe_emit(on_event, {
                    "type": "agent_completed",
                    "agent": agent_name,
                    "content": None,
                    "error": str(e),
                    "elapsed_ms": round((time.monotonic() - t0) * 1000),
                })
                tool_results.append({
                    "type": "tool_result",
                    "tool_use_id": block.id,
                    "content": f"Agent execution failed: {e}",
                    "is_error": True,
                })
                # 실패해도 approval_queue 소비 (UI가 멈추지 않도록)
                if approval_queue is not None:
                    await approval_queue.get()

        messages.append({"role": "user", "content": tool_results})

    else:
        logger.warning(f"[{request.task_id}] Reached MAX_ITERATIONS ({MAX_ITERATIONS})")

    if not run.final_output:
        for result in reversed(run.agent_results):
            if result.success and result.content:
                run.final_output = result.content
                break

    run.status = "completed" if run.final_output else "failed"
    run.completed_at = datetime.utcnow()
    run.total_tokens = sum(r.tokens_used for r in run.agent_results)
    return run


async def _safe_emit(
    on_event: Callable[[dict[str, Any]], Awaitable[None]] | None,
    payload: dict[str, Any],
) -> None:
    """on_event 콜백을 안전하게 호출 — 실패해도 워크플로우는 계속."""
    if on_event is None:
        return
    try:
        await on_event(payload)
    except Exception as e:
        logger.warning(f"on_event callback failed: {e}")


def _get_tool_schema_properties(agent_name: str) -> set[str]:
    for tool in TOOL_DEFINITIONS:
        if tool["name"] == agent_name:
            return set(tool["input_schema"].get("properties", {}).keys())
    return set()
