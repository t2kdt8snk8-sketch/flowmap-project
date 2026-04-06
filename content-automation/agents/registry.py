from __future__ import annotations

from collections.abc import Awaitable, Callable
from typing import Any

from core.models import AgentName, AgentResult, TaskRequest

# Type alias for all agent callables
AgentCallable = Callable[[TaskRequest, dict[str, Any]], Awaitable[AgentResult]]

# Tool definitions sent to Opus — each sub-agent is one tool.
# All agents include an optional "context" property so the orchestrator
# can pass accumulated results from earlier agents automatically.
TOOL_DEFINITIONS: list[dict[str, Any]] = [
    {
        "name": AgentName.RESEARCH,
        "description": (
            "Search the web for current trends, news, and data relevant to the topic. "
            "Returns a synthesized research report with key findings and trending context. "
            "Use this first when fresh real-world data or trend information is needed."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "query": {
                    "type": "string",
                    "description": "The search query or topic to research",
                },
                "focus": {
                    "type": "string",
                    "enum": ["trends", "news", "general"],
                    "description": "Research focus: 'trends' for viral/trending, 'news' for recent news, 'general' for broad info",
                },
                "context": {
                    "type": "string",
                    "description": "Additional context from prior agents (auto-injected)",
                },
            },
            "required": ["query"],
        },
    },
    {
        "name": AgentName.COPY,
        "description": (
            "Write marketing copy, captions, or text content in Korean and/or English. "
            "Specializes in Instagram captions, carousel text, ad copy, and social media posts. "
            "Use when compelling written content is the primary deliverable."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "content_type": {
                    "type": "string",
                    "enum": [
                        "instagram_caption",
                        "carousel_text",
                        "ad_copy",
                        "tagline",
                        "general",
                    ],
                    "description": "Type of copy to write",
                },
                "topic": {
                    "type": "string",
                    "description": "The subject or theme of the copy",
                },
                "language": {
                    "type": "string",
                    "enum": ["korean", "english", "both"],
                    "description": "Output language (default: both)",
                },
                "tone": {
                    "type": "string",
                    "enum": ["casual", "professional", "hype", "emotional"],
                    "description": "Tone and energy of the copy (default: casual)",
                },
                "context": {
                    "type": "string",
                    "description": "Research findings or prior agent output to incorporate",
                },
            },
            "required": ["content_type", "topic"],
        },
    },
    {
        "name": AgentName.IMAGE_PROMPT,
        "description": (
            "Generate detailed image generation prompts for Midjourney or Flux. "
            "Returns 3-5 ready-to-use prompts with style, lighting, and composition details. "
            "Use when visual content or cover images are needed alongside the text."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "subject": {
                    "type": "string",
                    "description": "Main subject or theme for the images",
                },
                "style": {
                    "type": "string",
                    "enum": [
                        "photorealistic",
                        "illustration",
                        "cinematic",
                        "minimal",
                        "artistic",
                    ],
                    "description": "Visual style (default: photorealistic)",
                },
                "platform": {
                    "type": "string",
                    "enum": ["midjourney", "flux", "generic"],
                    "description": "Target image generation platform (default: generic)",
                },
                "count": {
                    "type": "integer",
                    "description": "Number of prompts to generate (1-5, default: 3)",
                    "minimum": 1,
                    "maximum": 5,
                },
                "context": {
                    "type": "string",
                    "description": "Content context from prior agents",
                },
            },
            "required": ["subject"],
        },
    },
    {
        "name": AgentName.SCRIPT,
        "description": (
            "Write video scripts for YouTube, TikTok, Instagram Reels, or podcasts. "
            "Returns a structured script with hook, main sections, and CTA. "
            "Use when video or audio content is the primary deliverable."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "platform": {
                    "type": "string",
                    "enum": ["youtube", "tiktok", "reels", "podcast"],
                    "description": "Target platform",
                },
                "topic": {
                    "type": "string",
                    "description": "Subject of the script",
                },
                "duration_seconds": {
                    "type": "integer",
                    "description": "Target video duration in seconds (default: 60)",
                },
                "language": {
                    "type": "string",
                    "enum": ["korean", "english", "both"],
                    "description": "Script language (default: english)",
                },
                "context": {
                    "type": "string",
                    "description": "Research findings or content context",
                },
            },
            "required": ["platform", "topic"],
        },
    },
    {
        "name": AgentName.FORMAT,
        "description": (
            "Format and consolidate all outputs into a clean, structured final result. "
            "Returns polished markdown or JSON. "
            "ALWAYS call this as the very last step to finalize the output."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "content_to_format": {
                    "type": "string",
                    "description": "All collected content from previous agents",
                },
                "output_format": {
                    "type": "string",
                    "enum": ["markdown", "json"],
                    "description": "Output format (default: markdown)",
                },
                "task_summary": {
                    "type": "string",
                    "description": "One-line summary of what was accomplished",
                },
                "context": {
                    "type": "string",
                    "description": "Not used by format agent — ignored",
                },
            },
            "required": ["content_to_format"],
        },
    },
]

# Name → enum value lookup for quick validation
_TOOL_NAMES = {t["name"] for t in TOOL_DEFINITIONS}


def get_agent_callable(name: str) -> AgentCallable:
    """Return the async callable for a given agent name string."""
    from agents import (
        copy_agent,
        format_agent,
        image_prompt_agent,
        research_agent,
        script_agent,
    )

    mapping: dict[str, AgentCallable] = {
        AgentName.RESEARCH: research_agent.run,
        AgentName.COPY: copy_agent.run,
        AgentName.IMAGE_PROMPT: image_prompt_agent.run,
        AgentName.SCRIPT: script_agent.run,
        AgentName.FORMAT: format_agent.run,
    }
    agent_name = AgentName(name)
    if agent_name not in mapping:
        raise ValueError(f"Unknown agent: {name}")
    return mapping[agent_name]
