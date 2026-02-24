"""Integration tests for main entry point."""

import asyncio
import contextlib
import os
from unittest.mock import AsyncMock, patch

import aiohttp
import pytest
import yaml

from elephant.main import run


@pytest.fixture
def integration_env(tmp_path, sample_config):
    """Set up a complete environment for integration testing."""
    return {"config_path": sample_config}


async def _start_app(integration_env, port):
    """Helper to start the app as a background task."""

    async def run_app():
        await run(
            config_path=integration_env["config_path"],
            port=port,
        )

    task = asyncio.create_task(run_app())
    await asyncio.sleep(0.3)
    return task


async def _stop_app(task):
    """Helper to cancel and wait for cleanup."""
    task.cancel()
    with contextlib.suppress(asyncio.CancelledError):
        await task


def _data_dir_from_config(config_path: str) -> str:
    """Read the first database's data_dir from a config file."""
    with open(config_path) as f:
        raw = yaml.safe_load(f)
    first_db = next(iter(raw["databases"].values()))
    return first_db["data_dir"]


class TestMainIntegration:
    async def test_startup_and_health(self, integration_env, unused_tcp_port):
        """Test that the app starts, health works, and shuts down cleanly."""
        port = unused_tcp_port
        task = await _start_app(integration_env, port)

        async with (
            aiohttp.ClientSession() as session,
            session.get(f"http://localhost:{port}/health") as resp,
        ):
            assert resp.status == 200
            data = await resp.json()
            assert data["status"] == "ok"

        await _stop_app(task)

    async def test_creates_data_structure(self, integration_env, unused_tcp_port):
        """Test that data directories and schemas are created."""
        task = await _start_app(integration_env, unused_tcp_port)

        data_dir = _data_dir_from_config(integration_env["config_path"])
        assert os.path.isdir(os.path.join(data_dir, "events"))
        assert os.path.isdir(os.path.join(data_dir, "photo_index"))
        assert os.path.exists(os.path.join(data_dir, "events", "_schema.yaml"))
        assert os.path.isdir(os.path.join(data_dir, "people"))
        assert os.path.exists(os.path.join(data_dir, "people", "_schema.yaml"))

        await _stop_app(task)

    async def test_initializes_git(self, integration_env, unused_tcp_port):
        """Test that git repo is initialized with initial commit."""
        task = await _start_app(integration_env, unused_tcp_port)

        data_dir = _data_dir_from_config(integration_env["config_path"])
        assert os.path.isdir(os.path.join(data_dir, ".git"))

        await _stop_app(task)


def _write_telegram_config(
    tmp_path,
    webhook_url: str = "https://myhost.ngrok.io",
    mode: str = "webhook",
) -> str:
    """Write a telegram-provider config and return the path."""
    data_dir = str(tmp_path / "data")
    os.makedirs(data_dir, exist_ok=True)
    config = {
        "llm": {"base_url": "https://api.example.com/v1", "api_key": "test-key"},
        "messaging": {
            "provider": "telegram",
            "telegram": {
                "bot_token": "123:ABC",
                "webhook_secret": "secret123",
                "webhook_url": webhook_url,
                "mode": mode,
            },
        },
        "databases": {
            "default": {
                "data_dir": data_dir,
                "auth_secret": "456",
            },
        },
    }
    path = str(tmp_path / "config.yaml")
    with open(path, "w") as f:
        yaml.dump(config, f)
    return path


class TestWebhookValidation:
    async def test_startup_exits_on_webhook_mismatch(self, tmp_path):
        """App should exit(1) when registered webhook doesn't match config."""
        config_path = _write_telegram_config(tmp_path)

        wrong_url = "https://wrong-host.example.com/webhook/telegram/secret123"
        mock_info = {"ok": True, "result": {"url": wrong_url}}

        with (
            patch("elephant.telegram_api.get_webhook_info", return_value=mock_info),
            patch("elephant.telegram_api.build_webhook_url", return_value="https://myhost.ngrok.io/webhook/telegram/secret123"),
            pytest.raises(SystemExit) as exc_info,
        ):
            await run(config_path=config_path)

        assert exc_info.value.code == 1

    async def test_startup_continues_on_webhook_match(self, tmp_path, unused_tcp_port):
        """App should start normally when webhook matches config."""
        config_path = _write_telegram_config(tmp_path)

        correct_url = "https://myhost.ngrok.io/webhook/telegram/secret123"
        mock_info = {"ok": True, "result": {"url": correct_url}}

        with (
            patch("elephant.telegram_api.get_webhook_info", return_value=mock_info),
            patch("elephant.telegram_api.build_webhook_url", return_value=correct_url),
        ):
            task = asyncio.create_task(
                run(config_path=config_path, port=unused_tcp_port)
            )
            await asyncio.sleep(0.3)

            async with (
                aiohttp.ClientSession() as session,
                session.get(f"http://localhost:{unused_tcp_port}/health") as resp,
            ):
                assert resp.status == 200

            task.cancel()
            with contextlib.suppress(asyncio.CancelledError):
                await task

    async def test_startup_skips_check_when_no_webhook_url(self, tmp_path, unused_tcp_port):
        """App should start normally when webhook_url is empty in config."""
        config_path = _write_telegram_config(tmp_path, webhook_url="")

        # Should not call get_webhook_info at all
        with patch("elephant.telegram_api.get_webhook_info") as mock_get_info:
            task = asyncio.create_task(
                run(config_path=config_path, port=unused_tcp_port)
            )
            await asyncio.sleep(0.3)
            mock_get_info.assert_not_called()

            task.cancel()
            with contextlib.suppress(asyncio.CancelledError):
                await task


class TestPollingMode:
    async def test_polling_mode_deletes_webhook(self, tmp_path, unused_tcp_port):
        """Polling mode should call delete_webhook and skip webhook validation."""
        config_path = _write_telegram_config(tmp_path, mode="polling")

        with (
            patch("elephant.telegram_api.delete_webhook") as mock_delete,
            patch("elephant.telegram_api.get_webhook_info") as mock_get_info,
            patch(
                "elephant.polling.telegram.TelegramPoller.start",
                new_callable=AsyncMock,
            ) as mock_start,
            patch(
                "elephant.polling.telegram.TelegramPoller.stop",
                new_callable=AsyncMock,
            ),
        ):
            task = asyncio.create_task(
                run(config_path=config_path, port=unused_tcp_port)
            )
            await asyncio.sleep(0.3)

            mock_delete.assert_called_once_with("123:ABC")
            mock_get_info.assert_not_called()
            mock_start.assert_awaited_once()

            task.cancel()
            with contextlib.suppress(asyncio.CancelledError):
                await task

    async def test_polling_mode_no_webhook_route(self, tmp_path, unused_tcp_port):
        """Polling mode should not register the webhook route."""
        config_path = _write_telegram_config(tmp_path, mode="polling")

        with (
            patch("elephant.telegram_api.delete_webhook"),
            patch("elephant.polling.telegram.TelegramPoller.start", new_callable=AsyncMock),
            patch("elephant.polling.telegram.TelegramPoller.stop", new_callable=AsyncMock),
        ):
            task = asyncio.create_task(
                run(config_path=config_path, port=unused_tcp_port)
            )
            await asyncio.sleep(0.3)

            async with aiohttp.ClientSession() as session:
                # Health should work
                async with session.get(f"http://localhost:{unused_tcp_port}/health") as resp:
                    assert resp.status == 200

                # Webhook route should NOT exist
                wh_url = f"http://localhost:{unused_tcp_port}/webhook/telegram/secret123"
                async with session.post(wh_url) as resp:
                    assert resp.status == 404

            task.cancel()
            with contextlib.suppress(asyncio.CancelledError):
                await task
