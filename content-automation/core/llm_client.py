from __future__ import annotations

from functools import lru_cache
from typing import Any

import anthropic

from config.settings import get_settings


@lru_cache
def get_client() -> anthropic.AsyncAnthropic:
    settings = get_settings()
    return anthropic.AsyncAnthropic(
        api_key=settings.anthropic_api_key,
        base_url=settings.llm_base_url,
        max_retries=2,
        timeout=120.0,
    )


async def call_sonnet(system: str, messages: list[dict[str, Any]]) -> str:
    """Call Sonnet for generation tasks. Returns text content."""
    settings = get_settings()
    client = get_client()
    response = await client.messages.create(
        model=settings.model_sonnet,
        max_tokens=4096,
        system=system,
        messages=messages,
    )
    return response.content[0].text  # type: ignore[union-attr]


async def call_haiku(system: str, messages: list[dict[str, Any]]) -> str:
    """Call Haiku for cheap formatting tasks."""
    settings = get_settings()
    client = get_client()
    response = await client.messages.create(
        model=settings.model_haiku,
        max_tokens=2048,
        system=system,
        messages=messages,
    )
    return response.content[0].text  # type: ignore[union-attr]


async def call_opus_with_tools(
    system: str,
    messages: list[dict[str, Any]],
    tools: list[dict[str, Any]],
) -> anthropic.types.Message:
    """Call Opus with tool definitions for orchestration. Returns raw Message."""
    settings = get_settings()
    client = get_client()
    return await client.messages.create(
        model=settings.model_opus,
        max_tokens=4096,
        system=system,
        messages=messages,
        tools=tools,  # type: ignore[arg-type]
    )
