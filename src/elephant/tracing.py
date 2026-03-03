"""Message processing tracing: models + contextvar API."""

from __future__ import annotations

import contextvars
import logging
import uuid
from datetime import UTC, datetime
from typing import Any, Literal

from pydantic import BaseModel, Field

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Step models
# ---------------------------------------------------------------------------


class LLMCallStep(BaseModel):
    step_type: Literal["llm_call"] = "llm_call"
    timestamp: datetime = Field(default_factory=lambda: datetime.now(UTC))
    method: str = ""  # "chat" or "chat_with_tools"
    model: str = ""
    temperature: float = 0.7
    max_tokens: int = 1024
    messages: list[dict[str, Any]] = Field(default_factory=list)
    response_content: str | None = None
    response_tool_calls: list[dict[str, Any]] = Field(default_factory=list)
    usage: dict[str, int] = Field(default_factory=dict)


class ToolExecStep(BaseModel):
    step_type: Literal["tool_exec"] = "tool_exec"
    timestamp: datetime = Field(default_factory=lambda: datetime.now(UTC))
    tool_call_id: str = ""
    function_name: str = ""
    arguments: str = ""
    result: str = ""


class GitCommitStep(BaseModel):
    step_type: Literal["git_commit"] = "git_commit"
    timestamp: datetime = Field(default_factory=lambda: datetime.now(UTC))
    sha: str = ""
    message: str = ""


class IntentStep(BaseModel):
    step_type: Literal["intent"] = "intent"
    timestamp: datetime = Field(default_factory=lambda: datetime.now(UTC))
    resolved_intent: str = ""
    message_text: str = ""
    sender: str = ""


TraceStep = LLMCallStep | ToolExecStep | GitCommitStep | IntentStep

# ---------------------------------------------------------------------------
# Trace model
# ---------------------------------------------------------------------------


class Trace(BaseModel):
    trace_id: str = Field(default_factory=lambda: uuid.uuid4().hex[:16])
    database_name: str = ""
    message_id: str = ""
    sender: str = ""
    message_text: str = ""
    started_at: datetime = Field(default_factory=lambda: datetime.now(UTC))
    finished_at: datetime | None = None
    intent: str = ""
    final_response: str = ""
    steps: list[TraceStep] = Field(default_factory=list)
    error: str | None = None

# ---------------------------------------------------------------------------
# Contextvar API
# ---------------------------------------------------------------------------

_current_trace: contextvars.ContextVar[Trace | None] = contextvars.ContextVar(
    "current_trace", default=None,
)


def start_trace(
    database_name: str,
    message_id: str,
    sender: str,
    message_text: str,
) -> Trace:
    """Create a new trace and set it as the current trace."""
    trace = Trace(
        database_name=database_name,
        message_id=message_id,
        sender=sender,
        message_text=message_text,
    )
    _current_trace.set(trace)
    logger.debug("Trace started: %s", trace.trace_id)
    return trace


def record_step(step: TraceStep) -> None:
    """Append a step to the current trace. No-op if no trace is active."""
    trace = _current_trace.get()
    if trace is None:
        return
    trace.steps.append(step)


def finish_trace(
    intent: str = "",
    final_response: str = "",
    error: str | None = None,
) -> Trace | None:
    """Finalize the current trace and clear the contextvar. Returns the trace."""
    trace = _current_trace.get()
    if trace is None:
        return None
    trace.finished_at = datetime.now(UTC)
    trace.intent = intent or trace.intent
    trace.final_response = final_response or trace.final_response
    trace.error = error
    _current_trace.set(None)
    logger.debug("Trace finished: %s", trace.trace_id)
    return trace


def get_current_trace() -> Trace | None:
    """Return the active trace, or None."""
    return _current_trace.get()
