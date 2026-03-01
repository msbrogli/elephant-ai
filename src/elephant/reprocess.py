"""Replay raw messages against a fresh database."""

from __future__ import annotations

import argparse
import asyncio
import logging
import os
import shutil

import aiohttp

from elephant.config import load_config
from elephant.data.store import DataStore
from elephant.flows.anytime_log import AnytimeLogFlow
from elephant.git_ops import GitRepo
from elephant.llm.client import LLMClient
from elephant.messaging.base import Attachment, IncomingMessage, SendResult

logger = logging.getLogger(__name__)


class NullMessagingClient:
    """No-op messaging client — suppresses all outgoing messages during replay."""

    async def send_text(self, text: str) -> SendResult:
        return SendResult(success=True)

    async def send_text_with_media(self, text: str, media_url: str) -> SendResult:
        return SendResult(success=True)

    async def send_chat_action(self, action: str = "typing") -> None:
        pass

    async def broadcast_text(self, text: str) -> list[SendResult]:
        return [SendResult(success=True)]


async def reprocess(
    source_data_dir: str,
    target_data_dir: str,
    config_path: str | None = None,
) -> None:
    """Replay all raw messages from source into a fresh target database."""
    # 1. Read raw messages from source
    source_store = DataStore(source_data_dir)
    raw_msgs = source_store.read_raw_messages()
    messages = sorted(raw_msgs, key=lambda m: m.timestamp)
    logger.info("Loaded %d raw messages from %s", len(messages), source_data_dir)

    if not messages:
        logger.warning("No raw messages to replay.")
        return

    # 2. Copy media/ and preferences from source to target
    os.makedirs(target_data_dir, exist_ok=True)

    source_media = os.path.join(source_data_dir, "media")
    target_media = os.path.join(target_data_dir, "media")
    if os.path.isdir(source_media):
        if os.path.exists(target_media):
            shutil.rmtree(target_media)
        shutil.copytree(source_media, target_media)
        logger.info("Copied media/ to target")

    # Copy preferences.yaml if it exists
    source_prefs = os.path.join(source_data_dir, "preferences.yaml")
    target_prefs = os.path.join(target_data_dir, "preferences.yaml")
    if os.path.isfile(source_prefs):
        shutil.copy2(source_prefs, target_prefs)
        logger.info("Copied preferences.yaml to target")

    # Copy people/ directory if it exists
    source_people = os.path.join(source_data_dir, "people")
    target_people = os.path.join(target_data_dir, "people")
    if os.path.isdir(source_people):
        if os.path.exists(target_people):
            shutil.rmtree(target_people)
        shutil.copytree(source_people, target_people)
        logger.info("Copied people/ to target")

    # 3. Initialize fresh target database
    target_store = DataStore(target_data_dir)
    target_store.initialize()

    # 4. Load config and create LLM client
    config = load_config(config_path)
    session = aiohttp.ClientSession()

    try:
        llm = LLMClient(session, config.llm.base_url, config.llm.api_key)
        git = GitRepo(target_data_dir)
        git.initialize()

        # 5. Create flow with NullMessagingClient
        flow = AnytimeLogFlow(
            store=target_store,
            llm=llm,
            parsing_model=config.llm.parsing_model,
            messaging=NullMessagingClient(),
            git=git,
        )

        # 6. Replay each message
        for i, raw in enumerate(messages, 1):
            incoming = IncomingMessage(
                text=raw.text,
                sender=raw.sender,
                message_id=raw.message_id,
                timestamp=raw.timestamp,
                reply_to_id=raw.reply_to_id,
                attachments=[
                    Attachment(file_path=a.file_path, media_type=a.media_type)
                    for a in raw.attachments
                ],
            )
            try:
                await flow.handle_message(incoming)
                logger.info("[%d/%d] Replayed: %s", i, len(messages), raw.text[:60])
            except Exception:
                logger.exception(
                    "[%d/%d] Failed to replay message %s",
                    i, len(messages), raw.message_id,
                )
    finally:
        await session.close()


def main() -> None:
    """CLI entry point for reprocessing."""
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    )

    parser = argparse.ArgumentParser(
        description="Replay raw messages against a fresh database",
    )
    parser.add_argument("source_dir", help="Source data directory with raw_messages.yaml")
    parser.add_argument("target_dir", help="Target data directory (will be initialized fresh)")
    parser.add_argument(
        "-c", "--config",
        default=None,
        help="Path to config.yaml (default: $CONFIG_PATH or /app/config/config.yaml)",
    )
    args = parser.parse_args()
    asyncio.run(reprocess(args.source_dir, args.target_dir, config_path=args.config))


if __name__ == "__main__":
    main()
