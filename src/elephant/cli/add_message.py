"""add-message subcommand: send a message through the full flow as if from Telegram."""

from __future__ import annotations

import asyncio
import sys
from datetime import UTC, datetime

import aiohttp

from elephant.config import load_config
from elephant.data.store import DataStore
from elephant.flows.anytime_log import AnytimeLogFlow
from elephant.git_ops import GitRepo
from elephant.llm.client import LLMClient
from elephant.messaging.base import IncomingMessage, SendResult, current_chat_id


class CLIMessagingClient:
    """Captures replies and prints them to stdout."""

    def __init__(self) -> None:
        self.replies: list[str] = []

    async def send_text(self, text: str) -> SendResult:
        self.replies.append(text)
        print(text)
        return SendResult(success=True, message_id="cli-0")

    async def send_text_with_media(self, text: str, media_url: str) -> SendResult:
        self.replies.append(f"{text}\n[media: {media_url}]")
        print(f"{text}\n[media: {media_url}]")
        return SendResult(success=True, message_id="cli-0")

    async def send_chat_action(self, action: str = "typing") -> None:
        pass

    async def broadcast_text(self, text: str) -> list[SendResult]:
        return [await self.send_text(text)]


def _err(text: str = "") -> None:
    print(text, file=sys.stderr)


async def _run(config_path: str, message: str, database: str | None) -> None:
    config = load_config(config_path)

    # Select database
    if database:
        db_cfg = None
        for db in config.databases:
            if db.name == database:
                db_cfg = db
                break
        if db_cfg is None:
            names = ", ".join(db.name for db in config.databases)
            _err(f"Error: database '{database}' not found. Available: {names}")
            sys.exit(1)
    else:
        db_cfg = config.databases[0]

    store = DataStore(db_cfg.data_dir)
    git = GitRepo(db_cfg.data_dir)
    messaging = CLIMessagingClient()

    # Find sender from authorized chats
    ac = store.read_authorized_chats()
    approved = [c for c in ac.chats if c.status == "approved"]
    if not approved:
        _err("Error: no approved chats found. Run the bot with Telegram first to register a chat.")
        sys.exit(1)

    sender = approved[0].chat_id

    _err(f"Database: {db_cfg.name} ({db_cfg.data_dir})")
    _err(f"Sender: {sender} ({approved[0].display_name or 'unknown'})")
    _err(f"Message: {message!r}")
    _err("")

    async with aiohttp.ClientSession() as session:
        llm = LLMClient(session, config.llm.base_url, config.llm.api_key)

        flow = AnytimeLogFlow(
            store=store,
            llm=llm,
            parsing_model=config.llm.parsing_model,
            messaging=messaging,
            git=git,
            history_limit=db_cfg.chat_history_limit,
        )

        incoming = IncomingMessage(
            text=message,
            sender=sender,
            message_id=f"cli-{int(datetime.now(UTC).timestamp())}",
            timestamp=datetime.now(UTC),
        )

        token = current_chat_id.set(sender)
        try:
            await flow.handle_message(incoming)
        finally:
            current_chat_id.reset(token)


def run_add_message(config_path: str, message: str, database: str | None) -> None:
    """Sync wrapper to run the async add-message flow."""
    asyncio.run(_run(config_path, message, database))
