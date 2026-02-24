"""Shared messaging types and protocol."""

from __future__ import annotations

import contextvars
from dataclasses import dataclass, field
from typing import TYPE_CHECKING, Protocol

if TYPE_CHECKING:
    from datetime import datetime

current_chat_id: contextvars.ContextVar[str | None] = contextvars.ContextVar(
    "current_chat_id", default=None
)


@dataclass
class Attachment:
    file_path: str  # local path after download
    media_type: str  # "photo", "video", "document"


@dataclass
class IncomingMessage:
    text: str
    sender: str
    message_id: str
    timestamp: datetime
    reply_to_id: str | None = None
    attachments: list[Attachment] = field(default_factory=list)


@dataclass
class SendResult:
    success: bool
    message_id: str | None = None
    error: str | None = None
    raw: dict[str, object] = field(default_factory=dict)


class MessagingClient(Protocol):
    """Protocol for messaging clients."""

    async def send_text(self, text: str) -> SendResult: ...

    async def send_text_with_media(self, text: str, media_url: str) -> SendResult: ...

    async def send_chat_action(self, action: str = "typing") -> None: ...

    async def broadcast_text(self, text: str) -> list[SendResult]: ...
