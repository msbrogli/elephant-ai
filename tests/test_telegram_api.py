"""Tests for telegram_api module."""

from __future__ import annotations

import json
from unittest.mock import MagicMock, patch

import pytest

from elephant.config import TelegramConfig
from elephant.telegram_api import (
    api_call,
    build_webhook_url,
    delete_webhook,
    get_me,
    get_updates,
    get_webhook_info,
    set_webhook,
)


@pytest.fixture
def mock_urlopen():
    """Mock urllib.request.urlopen to return JSON responses."""
    with patch("elephant.telegram_api.urllib.request.urlopen") as mock:
        yield mock


def _make_response(data: dict) -> MagicMock:
    """Create a mock HTTP response that returns JSON data."""
    resp = MagicMock()
    resp.read.return_value = json.dumps(data).encode()
    resp.__enter__ = lambda s: s
    resp.__exit__ = MagicMock(return_value=False)
    return resp


class TestBuildWebhookUrl:
    def test_basic(self):
        config = TelegramConfig(
            bot_token="123:ABC",
            webhook_secret="sec123",
            webhook_url="https://myhost.ngrok.io",
        )
        assert build_webhook_url(config) == "https://myhost.ngrok.io/webhook/telegram/sec123"

    def test_strips_trailing_slash(self):
        config = TelegramConfig(
            bot_token="123:ABC",
            webhook_secret="sec123",
            webhook_url="https://myhost.ngrok.io/",
        )
        assert build_webhook_url(config) == "https://myhost.ngrok.io/webhook/telegram/sec123"


class TestApiCall:
    def test_success(self, mock_urlopen):
        expected = {"ok": True, "result": {"id": 123}}
        mock_urlopen.return_value = _make_response(expected)

        result = api_call("123:ABC", "getMe")

        assert result == expected
        mock_urlopen.assert_called_once()
        call_url = mock_urlopen.call_args[0][0]
        assert call_url == "https://api.telegram.org/bot123:ABC/getMe"


class TestGetMe:
    def test_calls_get_me(self, mock_urlopen):
        expected = {"ok": True, "result": {"username": "testbot"}}
        mock_urlopen.return_value = _make_response(expected)

        result = get_me("123:ABC")

        assert result == expected


class TestGetWebhookInfo:
    def test_calls_get_webhook_info(self, mock_urlopen):
        expected = {"ok": True, "result": {"url": "https://example.com/webhook"}}
        mock_urlopen.return_value = _make_response(expected)

        result = get_webhook_info("123:ABC")

        assert result == expected


class TestSetWebhook:
    def test_calls_set_webhook(self, mock_urlopen):
        expected = {"ok": True, "result": True}
        mock_urlopen.return_value = _make_response(expected)

        result = set_webhook("123:ABC", "https://example.com/webhook")

        assert result == expected
        call_url = mock_urlopen.call_args[0][0]
        assert "setWebhook?url=" in call_url


class TestDeleteWebhook:
    def test_calls_delete_webhook(self, mock_urlopen):
        expected = {"ok": True, "result": True}
        mock_urlopen.return_value = _make_response(expected)

        result = delete_webhook("123:ABC")

        assert result == expected


class TestGetUpdates:
    def test_calls_get_updates(self, mock_urlopen):
        expected = {"ok": True, "result": []}
        mock_urlopen.return_value = _make_response(expected)

        result = get_updates("123:ABC")

        assert result == expected

    def test_custom_limit(self, mock_urlopen):
        expected = {"ok": True, "result": []}
        mock_urlopen.return_value = _make_response(expected)

        get_updates("123:ABC", limit=5)

        call_url = mock_urlopen.call_args[0][0]
        assert "limit=5" in call_url
