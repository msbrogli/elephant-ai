"""Tests for Twilio messaging client."""

from unittest.mock import AsyncMock, MagicMock

import pytest

from elephant.config import TwilioConfig
from elephant.messaging.twilio import TwilioClient


def _mock_response(status, body):
    resp = AsyncMock()
    resp.status = status
    resp.json = AsyncMock(return_value=body)
    resp.__aenter__ = AsyncMock(return_value=resp)
    resp.__aexit__ = AsyncMock(return_value=False)
    return resp


@pytest.fixture
def twilio_config():
    return TwilioConfig(
        account_sid="AC123",
        auth_token="tok456",
        whatsapp_from="whatsapp:+1415000",
        whatsapp_to="whatsapp:+1972000",
    )


class TestTwilioClient:
    async def test_send_text_success(self, twilio_config):
        session = AsyncMock()
        session.post = MagicMock(
            return_value=_mock_response(201, {"sid": "SM123", "status": "queued"})
        )
        client = TwilioClient(session, twilio_config)

        result = await client.send_text("Hello!")
        assert result.success is True
        assert result.message_id == "SM123"

    async def test_send_text_failure(self, twilio_config):
        session = AsyncMock()
        session.post = MagicMock(
            return_value=_mock_response(400, {"message": "Invalid number"})
        )
        client = TwilioClient(session, twilio_config)

        result = await client.send_text("Hello!")
        assert result.success is False
        assert "Invalid number" in result.error

    async def test_send_text_with_media(self, twilio_config):
        session = AsyncMock()
        session.post = MagicMock(
            return_value=_mock_response(201, {"sid": "SM456"})
        )
        client = TwilioClient(session, twilio_config)

        result = await client.send_text_with_media("Look!", "https://example.com/photo.jpg")
        assert result.success is True
        assert result.message_id == "SM456"

    async def test_send_handles_exception(self, twilio_config):
        import aiohttp

        session = AsyncMock()
        session.post = MagicMock(side_effect=aiohttp.ClientError("Connection failed"))
        client = TwilioClient(session, twilio_config)

        result = await client.send_text("Hello!")
        assert result.success is False
        assert "Connection failed" in result.error
