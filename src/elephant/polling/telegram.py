"""Telegram long-polling receiver."""

from __future__ import annotations

import asyncio
import contextlib
import json
import logging
from datetime import UTC, datetime
from typing import TYPE_CHECKING, Any

import aiohttp

from elephant.data.models import AuthorizedChat
from elephant.messaging.base import Attachment, IncomingMessage, current_chat_id
from elephant.telegram_media import download_telegram_file, extract_text_and_files

if TYPE_CHECKING:
    from elephant.config import TelegramConfig
    from elephant.router import ChatRouter

logger = logging.getLogger(__name__)

BOT_API = "https://api.telegram.org"


class TelegramPoller:
    """Long-poll Telegram getUpdates and dispatch messages."""

    def __init__(
        self,
        session: aiohttp.ClientSession,
        config: TelegramConfig,
        router: ChatRouter,
    ) -> None:
        self._session = session
        self._config = config
        self._router = router
        self._offset: int = 0
        self._task: asyncio.Task[None] | None = None

    async def start(self) -> None:
        """Launch the background polling task."""
        self._task = asyncio.create_task(self._poll_loop())
        logger.info("Telegram polling started")

    async def stop(self) -> None:
        """Cancel the polling task."""
        if self._task is not None:
            self._task.cancel()
            with contextlib.suppress(asyncio.CancelledError):
                await self._task
            self._task = None
            logger.info("Telegram polling stopped")

    async def _reply(self, chat_id: str, text: str) -> None:
        """Send a short reply via the Bot API."""
        url = f"{BOT_API}/bot{self._config.bot_token}/sendMessage"
        payload: dict[str, object] = {"chat_id": chat_id, "text": text}
        try:
            async with self._session.post(url, json=payload) as resp:
                body = await resp.json()
                if not body.get("ok"):
                    logger.warning("Telegram reply failed: %s", body.get("description"))
        except Exception:
            logger.warning("Failed to send reply to %s", chat_id, exc_info=True)

    async def _send_with_markup(
        self, chat_id: str, text: str, reply_markup: dict[str, Any]
    ) -> None:
        """Send a message with an inline keyboard."""
        url = f"{BOT_API}/bot{self._config.bot_token}/sendMessage"
        payload: dict[str, object] = {
            "chat_id": chat_id,
            "text": text,
            "reply_markup": reply_markup,
        }
        try:
            async with self._session.post(url, json=payload) as resp:
                body = await resp.json()
                if not body.get("ok"):
                    logger.warning("Markup send failed: %s", body.get("description"))
        except Exception:
            logger.warning("Failed to send markup message", exc_info=True)

    async def _answer_cq(self, callback_query_id: str, text: str) -> None:
        """Answer a callback query."""
        url = f"{BOT_API}/bot{self._config.bot_token}/answerCallbackQuery"
        payload: dict[str, object] = {"callback_query_id": callback_query_id, "text": text}
        try:
            async with self._session.post(url, json=payload) as resp:
                await resp.json()
        except Exception:
            logger.warning("Failed to answer callback query", exc_info=True)

    async def _edit_message(self, chat_id: str, message_id: int, text: str) -> None:
        """Edit an existing message."""
        url = f"{BOT_API}/bot{self._config.bot_token}/editMessageText"
        payload: dict[str, object] = {
            "chat_id": chat_id,
            "message_id": message_id,
            "text": text,
        }
        try:
            async with self._session.post(url, json=payload) as resp:
                await resp.json()
        except Exception:
            logger.warning("Failed to edit message", exc_info=True)

    async def _handle_callback(self, callback_query: dict[str, Any]) -> None:
        """Handle an inline keyboard callback (approve/reject)."""
        cq_id = str(callback_query.get("id", ""))
        data_str = callback_query.get("data", "")
        cq_message = callback_query.get("message", {})
        cq_chat_id = str(cq_message.get("chat", {}).get("id", ""))
        cq_message_id = cq_message.get("message_id", 0)

        try:
            data = json.loads(data_str)
        except (json.JSONDecodeError, TypeError):
            await self._answer_cq(cq_id, "Invalid callback data.")
            return

        action = data.get("action")
        target_chat_id = data.get("chat_id", "")

        # Resolve db by approver's chat_id
        db = self._router.resolve_by_chat(cq_chat_id)
        if db is None:
            await self._answer_cq(cq_id, "You are not authorized.")
            return

        store = db.store
        ac = store.read_authorized_chats()
        approved_ids = {c.chat_id for c in ac.chats if c.status == "approved"}
        if cq_chat_id not in approved_ids:
            await self._answer_cq(cq_id, "You are not authorized.")
            return

        if action == "approve":
            for chat in ac.chats:
                if chat.chat_id == target_chat_id and chat.status == "pending":
                    chat.status = "approved"
                    store.write_authorized_chats(ac)
                    self._router.assign_chat(target_chat_id, db)
                    await self._answer_cq(cq_id, "Approved!")
                    await self._edit_message(
                        cq_chat_id, cq_message_id,
                        f"Chat {target_chat_id} has been approved.",
                    )
                    await self._reply(target_chat_id, "You have been approved!")
                    return
            await self._answer_cq(cq_id, "Chat not found or already approved.")

        elif action == "reject":
            ac.chats = [c for c in ac.chats if c.chat_id != target_chat_id]
            store.write_authorized_chats(ac)
            await self._answer_cq(cq_id, "Rejected.")
            await self._edit_message(
                cq_chat_id, cq_message_id,
                f"Chat {target_chat_id} has been rejected.",
            )
            await self._reply(target_chat_id, "Your request was rejected.")
        else:
            await self._answer_cq(cq_id, "Unknown action.")

    async def _poll_loop(self) -> None:
        """Continuously long-poll for updates."""
        base = f"{BOT_API}/bot{self._config.bot_token}"
        while True:
            try:
                params = {"offset": self._offset, "timeout": 30}
                async with self._session.get(
                    f"{base}/getUpdates",
                    params=params,
                    timeout=aiohttp.ClientTimeout(total=60),
                ) as resp:
                    data = await resp.json()

                if not data.get("ok"):
                    logger.warning("getUpdates error: %s", data.get("description"))
                    await asyncio.sleep(5)
                    continue

                for update in data.get("result", []):
                    update_id = update.get("update_id", 0)
                    self._offset = update_id + 1
                    await self._handle_update(update)

            except asyncio.CancelledError:
                raise
            except Exception:
                logger.exception("Polling error, retrying in 5s")
                await asyncio.sleep(5)

    async def _handle_update(self, update: dict[str, Any]) -> None:
        """Process a single Telegram update."""
        # Handle callback queries (inline keyboard buttons)
        callback_query = update.get("callback_query")
        if callback_query:
            await self._handle_callback(callback_query)
            return

        tg_message = update.get("message", {})
        text, file_infos = extract_text_and_files(tg_message)
        if not text and not file_infos:
            logger.debug(
                "Ignoring empty update from chat %s", tg_message.get("chat", {}).get("id")
            )
            return

        chat = tg_message.get("chat", {})
        sender = str(chat.get("id", ""))
        message_id = str(tg_message.get("message_id", ""))
        display_name = chat.get("title") or chat.get("first_name") or sender

        # Handle /start authentication with approval flow
        if text.startswith("/start "):
            provided_secret = text[len("/start "):]
            db = self._router.resolve_by_auth_secret(provided_secret)
            if db is None:
                logger.warning("Invalid /start secret from chat %s", sender)
                await self._reply(sender, "Invalid secret.")
                return

            store = db.store
            ac = store.read_authorized_chats()
            existing_ids = {c.chat_id for c in ac.chats}

            if sender in existing_ids:
                await self._reply(sender, "Already registered!")
                return

            approved_chats = [c for c in ac.chats if c.status == "approved"]

            if not approved_chats:
                # Bootstrap: first chat auto-approves
                ac.chats.append(
                    AuthorizedChat(
                        chat_id=sender,
                        status="approved",
                        added_at=datetime.now(UTC),
                        display_name=display_name,
                    )
                )
                store.write_authorized_chats(ac)
                self._router.assign_chat(sender, db)
                logger.info("Chat %s auto-approved (bootstrap) for db %s", sender, db.name)
                await self._reply(sender, "Authenticated!")
            else:
                # Add as pending, notify approved members
                ac.chats.append(
                    AuthorizedChat(
                        chat_id=sender,
                        status="pending",
                        added_at=datetime.now(UTC),
                        display_name=display_name,
                    )
                )
                store.write_authorized_chats(ac)
                await self._reply(
                    sender,
                    "Request sent! Waiting for approval from an existing member.",
                )
                keyboard = {
                    "inline_keyboard": [
                        [
                            {
                                "text": "Approve",
                                "callback_data": json.dumps(
                                    {"action": "approve", "chat_id": sender}
                                ),
                            },
                            {
                                "text": "Reject",
                                "callback_data": json.dumps(
                                    {"action": "reject", "chat_id": sender}
                                ),
                            },
                        ]
                    ]
                }
                for approved in approved_chats:
                    await self._send_with_markup(
                        approved.chat_id,
                        f"New chat wants to join: {display_name} (ID: {sender}). Approve?",
                        keyboard,
                    )
                logger.info("Chat %s added as pending for db %s", sender, db.name)
            return

        # Resolve database by sender chat_id
        db = self._router.resolve_by_chat(sender)
        if db is None:
            logger.debug("Ignoring message from unrouted chat %s", sender)
            return

        store = db.store

        # Verify sender is approved
        ac = store.read_authorized_chats()
        approved_ids = {c.chat_id for c in ac.chats if c.status == "approved"}
        if sender not in approved_ids:
            logger.debug("Ignoring message from unauthorized chat %s", sender)
            return

        # Download attached files
        attachments: list[Attachment] = []
        if file_infos:
            dest_dir = store.media_dir()
            for fi in file_infos:
                try:
                    local_path = await download_telegram_file(
                        self._session, self._config.bot_token, fi["file_id"], dest_dir
                    )
                    attachments.append(
                        Attachment(file_path=local_path, media_type=fi["media_type"])
                    )
                except Exception:
                    logger.warning(
                        "Failed to download file %s", fi["file_id"], exc_info=True
                    )

        # Check for reply
        reply_to = tg_message.get("reply_to_message")
        reply_to_id = str(reply_to.get("message_id", "")) if reply_to else None

        # Parse timestamp
        ts = tg_message.get("date", 0)
        timestamp = datetime.fromtimestamp(ts, tz=UTC) if ts else datetime.now(UTC)

        message = IncomingMessage(
            text=text,
            sender=sender,
            message_id=message_id,
            timestamp=timestamp,
            reply_to_id=reply_to_id,
            attachments=attachments,
        )

        token = current_chat_id.set(sender)
        try:
            await db.anytime.handle_message(message)
        except Exception:
            logger.exception("Error handling Telegram message")
            await self._reply(sender, "Sorry, something went wrong. Please try again.")
        finally:
            current_chat_id.reset(token)
