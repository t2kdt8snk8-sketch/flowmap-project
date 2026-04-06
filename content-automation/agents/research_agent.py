from __future__ import annotations

import asyncio
import time
from typing import Any

from loguru import logger

from core.llm_client import call_sonnet
from core.models import AgentName, AgentResult, TaskRequest

_SYSTEM = (
    "You are a research analyst specializing in music, culture, and social media trends. "
    "Synthesize the provided search results into a concise research report. "
    "Highlight key trends, viral moments, notable artists, and relevant context. "
    "Be factual and specific — include names, numbers, and dates where available."
)


async def run(request: TaskRequest, tool_input: dict[str, Any]) -> AgentResult:
    """Web search + trend analysis using DuckDuckGo, summarized by Sonnet."""
    t0 = time.monotonic()
    query = tool_input["query"]
    focus = tool_input.get("focus", "general")

    try:
        raw_results = await asyncio.to_thread(_ddg_search, query, focus)
    except Exception as e:
        logger.warning(f"DuckDuckGo search failed: {e} — returning empty results")
        raw_results = "No search results available."

    try:
        synthesis = await call_sonnet(
            system=_SYSTEM,
            messages=[
                {
                    "role": "user",
                    "content": (
                        f"Research query: {query}\n"
                        f"Focus: {focus}\n\n"
                        f"Search results:\n{raw_results}"
                    ),
                }
            ],
        )
    except Exception as e:
        return AgentResult(
            agent_name=AgentName.RESEARCH,
            success=False,
            content="",
            error=str(e),
            duration_ms=(time.monotonic() - t0) * 1000,
        )

    return AgentResult(
        agent_name=AgentName.RESEARCH,
        success=True,
        content=synthesis,
        duration_ms=(time.monotonic() - t0) * 1000,
    )


def _ddg_search(query: str, focus: str) -> str:
    """Synchronous DuckDuckGo search — must be called via asyncio.to_thread."""
    from duckduckgo_search import DDGS

    ddgs = DDGS()
    try:
        if focus == "trends" or focus == "news":
            results = ddgs.news(query, max_results=8)
        else:
            results = ddgs.text(query, max_results=8)
    except Exception:
        results = ddgs.text(query, max_results=5)

    if not results:
        return "No results found."

    lines = []
    for r in results:
        title = r.get("title", "")
        body = r.get("body", r.get("excerpt", ""))
        url = r.get("href", r.get("url", ""))
        lines.append(f"- {title}: {body} [{url}]")
    return "\n".join(lines)
