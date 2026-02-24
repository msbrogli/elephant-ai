"""Twilio WhatsApp messaging client."""

import logging
from urllib.parse import urlencode

import aiohttp

from elephant.config import TwilioConfig
from elephant.messaging.base import SendResult

logger = logging.getLogger(__name__)


class TwilioClient:
    """Send messages via Twilio REST API."""

    BASE_URL = "https://api.twilio.com/2010-04-01"

    def __init__(self, session: aiohttp.ClientSession, config: TwilioConfig) -> None:
        self._session = session
        self._config = config

    def _url(self) -> str:
        return f"{self.BASE_URL}/Accounts/{self._config.account_sid}/Messages.json"

    def _auth(self) -> aiohttp.BasicAuth:
        return aiohttp.BasicAuth(self._config.account_sid, self._config.auth_token)

    async def send_text(self, text: str) -> SendResult:
        """Send a WhatsApp text message."""
        data = {
            "From": self._config.whatsapp_from,
            "To": self._config.whatsapp_to,
            "Body": text,
        }
        return await self._send(data)

    async def send_text_with_media(self, text: str, media_url: str) -> SendResult:
        """Send a WhatsApp message with media."""
        data = {
            "From": self._config.whatsapp_from,
            "To": self._config.whatsapp_to,
            "Body": text,
            "MediaUrl": media_url,
        }
        return await self._send(data)

    async def send_chat_action(self, action: str = "typing") -> None:
        """Twilio does not support chat actions."""

    async def broadcast_text(self, text: str) -> list[SendResult]:
        """Broadcast sends to the single configured WhatsApp number."""
        result = await self.send_text(text)
        return [result]

    async def _send(self, data: dict[str, str]) -> SendResult:
        try:
            async with self._session.post(
                self._url(),
                data=urlencode(data),
                auth=self._auth(),
                headers={"Content-Type": "application/x-www-form-urlencoded"},
            ) as resp:
                body = await resp.json()
                if resp.status in (200, 201):
                    return SendResult(
                        success=True,
                        message_id=body.get("sid"),
                        raw=body,
                    )
                return SendResult(
                    success=False,
                    error=body.get("message", f"HTTP {resp.status}"),
                    raw=body,
                )
        except (aiohttp.ClientError, Exception) as e:
            logger.error("Twilio send failed: %s", e)
            return SendResult(success=False, error=str(e))
