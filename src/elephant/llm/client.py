"""OpenAI-compatible HTTP client with retry logic."""

import asyncio
import logging
from dataclasses import dataclass, field
from typing import Any

import aiohttp

logger = logging.getLogger(__name__)


class LLMError(Exception):
    """Base error for LLM operations."""


class LLMAuthError(LLMError):
    """Authentication failed (401/403)."""


@dataclass
class ToolCall:
    id: str
    function_name: str
    arguments: str  # raw JSON string


@dataclass
class LLMResponse:
    content: str | None
    model: str
    usage: dict[str, int]
    tool_calls: list[ToolCall] = field(default_factory=list)


class LLMClient:
    """OpenAI-compatible chat completions client."""

    RETRY_DELAYS = [1.0, 4.0, 16.0]

    def __init__(self, session: aiohttp.ClientSession, base_url: str, api_key: str) -> None:
        self._session = session
        self._base_url = base_url.rstrip("/")
        self._api_key = api_key

    async def _request(self, payload: dict[str, Any]) -> dict[str, Any]:
        """Send a request with retry on transient errors. Returns raw JSON."""
        url = f"{self._base_url}/chat/completions"
        headers = {
            "Authorization": f"Bearer {self._api_key}",
            "Content-Type": "application/json",
        }

        last_error: Exception | None = None
        for attempt, delay in enumerate([0.0, *self.RETRY_DELAYS]):
            if delay > 0:
                logger.warning("LLM retry attempt %d after %.1fs", attempt, delay)
                await asyncio.sleep(delay)

            try:
                async with self._session.post(url, json=payload, headers=headers) as resp:
                    if resp.status in (401, 403):
                        text = await resp.text()
                        raise LLMAuthError(f"Auth failed ({resp.status}): {text}")

                    if resp.status in (429, 500, 503):
                        text = await resp.text()
                        last_error = LLMError(f"Transient error ({resp.status}): {text}")
                        continue

                    if resp.status != 200:
                        text = await resp.text()
                        raise LLMError(f"LLM request failed ({resp.status}): {text}")

                    data: dict[str, Any] = await resp.json()
                    return data
            except (TimeoutError, aiohttp.ClientError) as e:
                last_error = LLMError(f"Connection error: {e}")
                continue

        raise last_error or LLMError("All retries exhausted")

    @staticmethod
    def _parse_response(data: dict[str, Any], model: str) -> LLMResponse:
        """Parse raw API JSON into LLMResponse."""
        choice = data["choices"][0]
        message = choice["message"]

        tool_calls: list[ToolCall] = []
        for tc in message.get("tool_calls") or []:
            tool_calls.append(
                ToolCall(
                    id=tc["id"],
                    function_name=tc["function"]["name"],
                    arguments=tc["function"]["arguments"],
                )
            )

        return LLMResponse(
            content=message.get("content"),
            model=data.get("model", model),
            usage=data.get("usage", {}),
            tool_calls=tool_calls,
        )

    async def chat(
        self,
        messages: list[dict[str, Any]],
        model: str,
        temperature: float = 0.7,
        max_tokens: int = 1024,
    ) -> LLMResponse:
        """Send a chat completion request with retry on transient errors."""
        payload = {
            "model": model,
            "messages": messages,
            "temperature": temperature,
            "max_tokens": max_tokens,
        }
        data = await self._request(payload)
        return self._parse_response(data, model)

    async def chat_with_tools(
        self,
        messages: list[dict[str, Any]],
        model: str,
        tools: list[dict[str, Any]],
        temperature: float = 0.7,
        max_tokens: int = 1024,
    ) -> LLMResponse:
        """Send a chat completion request with tool definitions."""
        payload = {
            "model": model,
            "messages": messages,
            "tools": tools,
            "temperature": temperature,
            "max_tokens": max_tokens,
        }
        data = await self._request(payload)
        return self._parse_response(data, model)
