"""Synchronous Telegram Bot API helpers for startup checks and CLI tools."""

from __future__ import annotations

import json
import urllib.parse
import urllib.request
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from elephant.config import TelegramConfig

BOT_API = "https://api.telegram.org"


def api_call(bot_token: str, method: str) -> dict[str, Any]:
    """Call a Telegram Bot API method and return the parsed JSON response."""
    url = f"{BOT_API}/bot{bot_token}/{method}"
    with urllib.request.urlopen(url, timeout=10) as resp:  # noqa: S310
        result: dict[str, Any] = json.loads(resp.read())
        return result


def get_me(bot_token: str) -> dict[str, Any]:
    """Get bot identity via getMe."""
    return api_call(bot_token, "getMe")


def get_webhook_info(bot_token: str) -> dict[str, Any]:
    """Get current webhook configuration."""
    return api_call(bot_token, "getWebhookInfo")


def set_webhook(bot_token: str, url: str) -> dict[str, Any]:
    """Register a webhook URL with Telegram."""
    encoded = urllib.parse.quote(url, safe="")
    return api_call(bot_token, f"setWebhook?url={encoded}")


def delete_webhook(bot_token: str) -> dict[str, Any]:
    """Remove the current webhook."""
    return api_call(bot_token, "deleteWebhook")


def get_updates(bot_token: str, limit: int = 10) -> dict[str, Any]:
    """Fetch pending updates (only works when webhook is not set)."""
    return api_call(bot_token, f"getUpdates?limit={limit}&timeout=0")


def build_webhook_url(config: TelegramConfig) -> str:
    """Build the full webhook URL from config."""
    base = config.webhook_url.rstrip("/")
    return f"{base}/webhook/telegram/{config.webhook_secret}"
