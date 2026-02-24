"""Tests for Telegram messaging client."""

from unittest.mock import AsyncMock, MagicMock

import pytest

from elephant.config import TelegramConfig
from elephant.data.models import AuthorizedChat, AuthorizedChatsFile, DigestState
from elephant.messaging.base import current_chat_id
from elephant.messaging.telegram import TelegramClient


def _mock_response(status, body):
    resp = AsyncMock()
    resp.status = status
    resp.json = AsyncMock(return_value=body)
    resp.__aenter__ = AsyncMock(return_value=resp)
    resp.__aexit__ = AsyncMock(return_value=False)
    return resp


def _mock_store(authorized_chat_id="456"):
    store = MagicMock()
    store.read_digest_state.return_value = DigestState(authorized_chat_id=authorized_chat_id)
    chats = []
    if authorized_chat_id:
        chats.append(AuthorizedChat(chat_id=authorized_chat_id, status="approved"))
    store.read_authorized_chats.return_value = AuthorizedChatsFile(chats=chats)
    return store


@pytest.fixture
def telegram_config():
    return TelegramConfig(
        bot_token="123:ABC",
        webhook_secret="secret123",
    )


class TestTelegramClient:
    async def test_send_text_success(self, telegram_config):
        session = AsyncMock()
        session.post = MagicMock(
            return_value=_mock_response(
                200, {"ok": True, "result": {"message_id": 42}}
            )
        )
        client = TelegramClient(session, telegram_config, _mock_store())

        result = await client.send_text("Hello!")
        assert result.success is True
        assert result.message_id == "42"

    async def test_send_text_failure(self, telegram_config):
        session = AsyncMock()
        session.post = MagicMock(
            return_value=_mock_response(
                400, {"ok": False, "description": "Bad Request: chat not found"}
            )
        )
        client = TelegramClient(session, telegram_config, _mock_store())

        result = await client.send_text("Hello!")
        assert result.success is False
        assert "chat not found" in result.error

    async def test_send_text_with_media(self, telegram_config):
        session = AsyncMock()
        session.post = MagicMock(
            return_value=_mock_response(
                200, {"ok": True, "result": {"message_id": 43}}
            )
        )
        client = TelegramClient(session, telegram_config, _mock_store())

        result = await client.send_text_with_media("Look!", "https://example.com/photo.jpg")
        assert result.success is True
        assert result.message_id == "43"

    async def test_send_handles_exception(self, telegram_config):
        import aiohttp

        session = AsyncMock()
        session.post = MagicMock(side_effect=aiohttp.ClientError("Timeout"))
        client = TelegramClient(session, telegram_config, _mock_store())

        result = await client.send_text("Hello!")
        assert result.success is False
        assert "Timeout" in result.error

    async def test_send_text_no_authorized_chat(self, telegram_config):
        session = AsyncMock()
        client = TelegramClient(session, telegram_config, _mock_store(authorized_chat_id=None))

        result = await client.send_text("Hello!")
        assert result.success is False
        assert result.error == "No authorized chat"

    async def test_send_text_with_media_no_authorized_chat(self, telegram_config):
        session = AsyncMock()
        client = TelegramClient(session, telegram_config, _mock_store(authorized_chat_id=None))

        result = await client.send_text_with_media("Look!", "https://example.com/photo.jpg")
        assert result.success is False
        assert result.error == "No authorized chat"

    async def test_get_chat_id_reads_contextvar(self, telegram_config):
        """When current_chat_id contextvar is set, _get_chat_id returns it."""
        session = AsyncMock()
        session.post = MagicMock(
            return_value=_mock_response(
                200, {"ok": True, "result": {"message_id": 44}}
            )
        )
        client = TelegramClient(session, telegram_config, _mock_store())

        token = current_chat_id.set("999")
        try:
            result = await client.send_text("Hello via contextvar!")
            assert result.success is True
            # Verify the payload was sent to chat 999, not 456
            call_args = session.post.call_args
            payload = call_args[1]["json"]
            assert payload["chat_id"] == "999"
        finally:
            current_chat_id.reset(token)

    async def test_send_chat_action_bool_result(self, telegram_config):
        """sendChatAction returns result: true (bool), not a dict."""
        session = AsyncMock()
        session.post = MagicMock(
            return_value=_mock_response(200, {"ok": True, "result": True})
        )
        client = TelegramClient(session, telegram_config, _mock_store())

        await client.send_chat_action("typing")
        session.post.assert_called_once()

    async def test_broadcast_text_sends_to_all_approved(self, telegram_config):
        """broadcast_text should send to all approved chats."""
        session = AsyncMock()
        session.post = MagicMock(
            return_value=_mock_response(
                200, {"ok": True, "result": {"message_id": 50}}
            )
        )
        store = MagicMock()
        store.read_authorized_chats.return_value = AuthorizedChatsFile(
            chats=[
                AuthorizedChat(chat_id="100", status="approved"),
                AuthorizedChat(chat_id="200", status="approved"),
                AuthorizedChat(chat_id="300", status="pending"),
            ]
        )
        client = TelegramClient(session, telegram_config, store)

        results = await client.broadcast_text("Hello everyone!")
        # Should send to 2 approved chats, not the pending one
        assert len(results) == 2
        assert all(r.success for r in results)
        assert session.post.call_count == 2

    async def test_broadcast_text_empty_chats(self, telegram_config):
        """broadcast_text with no approved chats returns empty list."""
        session = AsyncMock()
        store = MagicMock()
        store.read_authorized_chats.return_value = AuthorizedChatsFile(chats=[])
        client = TelegramClient(session, telegram_config, store)

        results = await client.broadcast_text("Hello!")
        assert results == []
        session.post.assert_not_called()
