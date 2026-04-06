from __future__ import annotations

import time
from typing import Any

from core.llm_client import call_sonnet
from core.models import AgentName, AgentResult, TaskRequest

_SYSTEM = (
    "You are an expert at writing image generation prompts for Midjourney and Flux. "
    "Your prompts are vivid, technically precise, and visually specific — "
    "detailing subject, style, lighting, composition, color palette, mood, and camera/lens when relevant. "
    "Each prompt should be self-contained and ready to paste directly into an image generator. "
    "Number each prompt clearly."
)


async def run(request: TaskRequest, tool_input: dict[str, Any]) -> AgentResult:
    """Generate detailed image prompts for Midjourney or Flux."""
    t0 = time.monotonic()
    subject = tool_input["subject"]
    style = tool_input.get("style", "photorealistic")
    platform = tool_input.get("platform", "generic")
    count = tool_input.get("count", 3)
    context = tool_input.get("context", "")

    prompt_parts = [
        f"Generate {count} image generation prompts for {platform}.",
        f"Subject: {subject}",
        f"Style: {style}",
    ]
    if context:
        prompt_parts.append(f"Context: {context}")

    if platform == "midjourney":
        prompt_parts.append(
            "End each prompt with Midjourney parameters like: --ar 4:5 --v 6 --style raw"
        )

    try:
        content = await call_sonnet(
            system=_SYSTEM,
            messages=[{"role": "user", "content": "\n".join(prompt_parts)}],
        )
    except Exception as e:
        return AgentResult(
            agent_name=AgentName.IMAGE_PROMPT,
            success=False,
            content="",
            error=str(e),
            duration_ms=(time.monotonic() - t0) * 1000,
        )

    return AgentResult(
        agent_name=AgentName.IMAGE_PROMPT,
        success=True,
        content=content,
        duration_ms=(time.monotonic() - t0) * 1000,
    )
