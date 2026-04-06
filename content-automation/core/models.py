from __future__ import annotations

import uuid
from datetime import datetime
from enum import Enum
from typing import Any

from pydantic import BaseModel, Field


class AgentName(str, Enum):
    RESEARCH = "research_agent"
    COPY = "copy_agent"
    IMAGE_PROMPT = "image_prompt_agent"
    SCRIPT = "script_agent"
    FORMAT = "format_agent"


class TaskRequest(BaseModel):
    task_id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    user_message: str
    chat_id: str
    created_at: datetime = Field(default_factory=datetime.utcnow)
    metadata: dict[str, Any] = Field(default_factory=dict)


class AgentResult(BaseModel):
    agent_name: AgentName
    success: bool
    content: str
    error: str | None = None
    tokens_used: int = 0
    duration_ms: float = 0.0


class WorkflowRun(BaseModel):
    task_id: str
    request: TaskRequest
    agent_results: list[AgentResult] = Field(default_factory=list)
    final_output: str | None = None
    status: str = "pending"
    started_at: datetime | None = None
    completed_at: datetime | None = None
    total_tokens: int = 0
