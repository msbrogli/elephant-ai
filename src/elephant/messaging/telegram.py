"""Telegram Bot API messaging client."""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING

import aiohttp

from elephant.messaging.base import SendResult

if TYPE_CHECKING:
    from elephant.config import TelegramConfig
    from elephant.data.store import DataStore

logger = logging.getLogger(__name__)


class TelegramClient:
    """Send messages via Telegram Bot API."""

    BASE_URL = "https://api.telegram.org"

    def __init__(
        self, session: aiohttp.ClientSession, config: TelegramConfig, store: DataStore
    ) -> None:
        self._session = session
        self._config = config
        self._store = store

    def _url(self, method: str) -> str:
        return f"{self.BASE_URL}/bot{self._config.bot_token}/{method}"

    def _get_chat_id(self) -> str | None:
        from elephant.messaging.base import current_chat_id

        chat_id = current_chat_id.get(None)
        if chat_id:
            return chat_id
        return self._store.read_digest_state().authorized_chat_id

    async def send_text(self, text: str) -> SendResult:
        """Send a text message."""
        chat_id = self._get_chat_id()
        if not chat_id:
            return SendResult(success=False, error="No authorized chat")
        payload: dict[str, object] = {
            "chat_id": chat_id,
            "text": text,
            "parse_mode": "Markdown",
        }
        return await self._call("sendMessage", payload)

    async def send_text_with_media(self, text: str, media_url: str) -> SendResult:
        """Send a photo with caption."""
        chat_id = self._get_chat_id()
        if not chat_id:
            return SendResult(success=False, error="No authorized chat")
        payload: dict[str, object] = {
            "chat_id": chat_id,
            "photo": media_url,
            "caption": text,
            "parse_mode": "Markdown",
        }
        return await self._call("sendPhoto", payload)

    async def send_chat_action(self, action: str = "typing") -> None:
        """Send a chat action (e.g. 'typing' indicator)."""
        chat_id = self._get_chat_id()
        if not chat_id:
            return
        await self._call("sendChatAction", {"chat_id": chat_id, "action": action})

    async def broadcast_text(self, text: str) -> list[SendResult]:
        """Send a text message to all approved chats."""
        chats = self._store.read_authorized_chats()
        results: list[SendResult] = []
        for chat in chats.chats:
            if chat.status == "approved":
                payload: dict[str, object] = {
                    "chat_id": chat.chat_id,
                    "text": text,
                    "parse_mode": "Markdown",
                }
                results.append(await self._call("sendMessage", payload))
        return results

    async def _call(self, method: str, payload: dict[str, object]) -> SendResult:
        try:
            async with self._session.post(self._url(method), json=payload) as resp:
                body = await resp.json()
                if body.get("ok"):
                    result = body.get("result", {})
                    message_id = ""
                    if isinstance(result, dict):
                        message_id = str(result.get("message_id", ""))
                    return SendResult(
                        success=True,
                        message_id=message_id,
                        raw=body,
                    )
                return SendResult(
                    success=False,
                    error=body.get("description", f"HTTP {resp.status}"),
                    raw=body,
                )
        except (aiohttp.ClientError, Exception) as e:
            logger.error("Telegram send failed: %s", e)
            return SendResult(success=False, error=str(e))
