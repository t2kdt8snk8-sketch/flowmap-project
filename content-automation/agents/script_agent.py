from __future__ import annotations

import time
from typing import Any

from core.llm_client import call_sonnet
from core.models import AgentName, AgentResult, TaskRequest

_SYSTEM = (
    "You are a video script writer specializing in music, culture, and lifestyle content. "
    "Structure every script with clearly labeled sections:\n"
    "- HOOK (first 3 seconds — must grab attention instantly)\n"
    "- INTRO (brief context)\n"
    "- SECTION 1, 2, 3... (main content, each with a clear point)\n"
    "- CTA (call to action — follow, like, comment, save)\n\n"
    "Match pacing to the platform: TikTok/Reels are punchy; YouTube allows depth. "
    "Include on-screen text suggestions in [brackets]."
)


async def run(request: TaskRequest, tool_input: dict[str, Any]) -> AgentResult:
    """Write a structured video script."""
    t0 = time.monotonic()
    platform = tool_input["platform"]
    topic = tool_input["topic"]
    duration = tool_input.get("duration_seconds", 60)
    language = tool_input.get("language", "english")
    context = tool_input.get("context", "")

    prompt_parts = [
        f"Write a {duration}-second {platform} video script about: {topic}",
        f"Language: {language}",
    ]
    if context:
        prompt_parts.append(f"\nResearch context:\n{context}")

    try:
        content = await call_sonnet(
            system=_SYSTEM,
            messages=[{"role": "user", "content": "\n".join(prompt_parts)}],
        )
    except Exception as e:
        return AgentResult(
            agent_name=AgentName.SCRIPT,
            success=False,
            content="",
            error=str(e),
            duration_ms=(time.monotonic() - t0) * 1000,
        )

    return AgentResult(
        agent_name=AgentName.SCRIPT,
        success=True,
        content=content,
        duration_ms=(time.monotonic() - t0) * 1000,
    )
