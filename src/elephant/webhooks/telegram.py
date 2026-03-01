"""Telegram webhook handler with secret path validation, /start approval flow."""

from __future__ import annotations

import json
import logging
from collections.abc import Awaitable, Callable
from datetime import UTC, datetime
from typing import TYPE_CHECKING, Any

import aiohttp
from aiohttp import web

from elephant.data.models import AuthorizedChat
from elephant.messaging.base import Attachment, IncomingMessage, current_chat_id
from elephant.telegram_media import download_telegram_file, extract_text_and_files

if TYPE_CHECKING:
    from elephant.router import ChatRouter

logger = logging.getLogger(__name__)

OnMessageCallback = Callable[[IncomingMessage], Awaitable[None]]

BOT_API = "https://api.telegram.org"

bot_token_key: web.AppKey[str] = web.AppKey("bot_token", str)
bot_session_key: web.AppKey[aiohttp.ClientSession] = web.AppKey(
    "bot_session", aiohttp.ClientSession
)
media_dir_key: web.AppKey[str] = web.AppKey("media_dir", str)


def create_telegram_webhook(
    webhook_secret: str,
    router: ChatRouter,
) -> web.RouteDef:
    """Create the Telegram webhook route with secret path validation."""

    async def _reply(
        request: web.Request, bot_token: str, chat_id: str, text: str
    ) -> None:
        """Send a short reply via the Bot API."""
        url = f"{BOT_API}/bot{bot_token}/sendMessage"
        payload: dict[str, object] = {"chat_id": chat_id, "text": text}
        try:
            async with request.app[bot_session_key].post(url, json=payload) as resp:
                body = await resp.json()
                if not body.get("ok"):
                    logger.warning("Telegram reply failed: %s", body.get("description"))
        except Exception:
            logger.warning("Failed to send reply to %s", chat_id, exc_info=True)

    async def _send_approval_request(
        request: web.Request,
        bot_token: str,
        target_chat_id: str,
        requester_chat_id: str,
        display_name: str,
    ) -> None:
        """Send an inline-keyboard approval request to an existing member."""
        url = f"{BOT_API}/bot{bot_token}/sendMessage"
        keyboard = {
            "inline_keyboard": [
                [
                    {
                        "text": "Approve",
                        "callback_data": json.dumps(
                            {"action": "approve", "chat_id": requester_chat_id}
                        ),
                    },
                    {
                        "text": "Reject",
                        "callback_data": json.dumps(
                            {"action": "reject", "chat_id": requester_chat_id}
                        ),
                    },
                ]
            ]
        }
        payload: dict[str, object] = {
            "chat_id": target_chat_id,
            "text": f"New chat wants to join: {display_name} (ID: {requester_chat_id}). Approve?",
            "reply_markup": keyboard,
        }
        try:
            async with request.app[bot_session_key].post(url, json=payload) as resp:
                body = await resp.json()
                if not body.get("ok"):
                    logger.warning("Approval request failed: %s", body.get("description"))
        except Exception:
            logger.warning("Failed to send approval request", exc_info=True)

    async def _answer_cq(
        request: web.Request, bot_token: str, callback_query_id: str, text: str
    ) -> None:
        """Answer a callback query."""
        url = f"{BOT_API}/bot{bot_token}/answerCallbackQuery"
        payload: dict[str, object] = {"callback_query_id": callback_query_id, "text": text}
        try:
            async with request.app[bot_session_key].post(url, json=payload) as resp:
                await resp.json()
        except Exception:
            logger.warning("Failed to answer callback query", exc_info=True)

    async def _edit_message(
        request: web.Request,
        bot_token: str,
        chat_id: str,
        message_id: int,
        text: str,
    ) -> None:
        """Edit an existing message (remove inline keyboard)."""
        url = f"{BOT_API}/bot{bot_token}/editMessageText"
        payload: dict[str, object] = {
            "chat_id": chat_id,
            "message_id": message_id,
            "text": text,
        }
        try:
            async with request.app[bot_session_key].post(url, json=payload) as resp:
                await resp.json()
        except Exception:
            logger.warning("Failed to edit message", exc_info=True)

    async def _handle_callback(
        request: web.Request, callback_query: dict[str, Any]
    ) -> None:
        """Handle an inline keyboard callback (approve/reject)."""
        bot_token = request.app[bot_token_key]
        cq_id = str(callback_query.get("id", ""))
        data_str = callback_query.get("data", "")
        cq_message = callback_query.get("message", {})
        cq_chat_id = str(cq_message.get("chat", {}).get("id", ""))
        cq_message_id = cq_message.get("message_id", 0)

        try:
            data = json.loads(data_str)
        except (json.JSONDecodeError, TypeError):
            await _answer_cq(request, bot_token, cq_id, "Invalid callback data.")
            return

        action = data.get("action")
        target_chat_id = data.get("chat_id", "")

        # Resolve db by the approver's chat_id
        db = router.resolve_by_chat(cq_chat_id)
        if db is None:
            await _answer_cq(request, bot_token, cq_id, "You are not authorized.")
            return

        store = db.store
        ac = store.read_authorized_chats()
        approved_ids = {c.chat_id for c in ac.chats if c.status == "approved"}
        if cq_chat_id not in approved_ids:
            await _answer_cq(request, bot_token, cq_id, "You are not authorized.")
            return

        if action == "approve":
            for chat in ac.chats:
                if chat.chat_id == target_chat_id and chat.status == "pending":
                    chat.status = "approved"
                    store.write_authorized_chats(ac)
                    router.assign_chat(target_chat_id, db)
                    await _answer_cq(request, bot_token, cq_id, "Approved!")
                    await _edit_message(
                        request, bot_token, cq_chat_id, cq_message_id,
                        f"Chat {target_chat_id} has been approved.",
                    )
                    await _reply(request, bot_token, target_chat_id, "You have been approved!")
                    return
            await _answer_cq(request, bot_token, cq_id, "Chat not found or already approved.")

        elif action == "reject":
            ac.chats = [c for c in ac.chats if c.chat_id != target_chat_id]
            store.write_authorized_chats(ac)
            await _answer_cq(request, bot_token, cq_id, "Rejected.")
            await _edit_message(
                request, bot_token, cq_chat_id, cq_message_id,
                f"Chat {target_chat_id} has been rejected.",
            )
            await _reply(request, bot_token, target_chat_id, "Your request was rejected.")
        else:
            await _answer_cq(request, bot_token, cq_id, "Unknown action.")

    async def handler(request: web.Request) -> web.Response:
        # Validate secret in URL path
        secret = request.match_info.get("secret", "")
        if secret != webhook_secret:
            logger.warning("Invalid Telegram webhook secret")
            return web.json_response({"error": "forbidden"}, status=403)

        try:
            data = await request.json()
        except Exception:
            return web.json_response({"error": "invalid json"}, status=400)

        # Handle callback queries (inline keyboard buttons)
        callback_query = data.get("callback_query")
        if callback_query:
            await _handle_callback(request, callback_query)
            return web.json_response({"ok": True})

        # Extract message from Telegram update
        tg_message = data.get("message", {})
        text, file_infos = extract_text_and_files(tg_message)
        if not text and not file_infos:
            logger.debug(
                "Ignoring empty update from chat %s", tg_message.get("chat", {}).get("id")
            )
            return web.json_response({"ok": True})

        chat = tg_message.get("chat", {})
        sender = str(chat.get("id", ""))
        message_id = str(tg_message.get("message_id", ""))
        display_name = (
            chat.get("title")
            or chat.get("first_name")
            or sender
        )

        # Handle /start authentication with approval flow
        if text.startswith("/start "):
            provided_secret = text[len("/start "):]
            db = router.resolve_by_auth_secret(provided_secret)
            if db is None:
                logger.warning("Invalid /start secret from chat %s", sender)
                await _reply(request, request.app[bot_token_key], sender, "Invalid secret.")
                return web.json_response({"ok": True})

            store = db.store
            ac = store.read_authorized_chats()
            existing_ids = {c.chat_id for c in ac.chats}

            if sender in existing_ids:
                await _reply(
                    request, request.app[bot_token_key], sender, "Already registered!"
                )
                return web.json_response({"ok": True})

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
                router.assign_chat(sender, db)
                logger.info("Chat %s auto-approved (bootstrap) for db %s", sender, db.name)
                await _reply(
                    request, request.app[bot_token_key], sender, "Authenticated!"
                )
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
                await _reply(
                    request,
                    request.app[bot_token_key],
                    sender,
                    "Request sent! Waiting for approval from an existing member.",
                )
                bot_token = request.app[bot_token_key]
                for approved in approved_chats:
                    await _send_approval_request(
                        request, bot_token, approved.chat_id, sender, display_name
                    )
                logger.info("Chat %s added as pending for db %s", sender, db.name)

            return web.json_response({"ok": True})

        # Resolve database by sender chat_id
        db = router.resolve_by_chat(sender)
        if db is None:
            logger.debug("Ignoring message from unrouted chat %s", sender)
            return web.json_response({"ok": True})

        store = db.store

        # Verify sender is approved in this database
        ac = store.read_authorized_chats()
        approved_ids = {c.chat_id for c in ac.chats if c.status == "approved"}
        if sender not in approved_ids:
            logger.debug("Ignoring message from unauthorized chat %s", sender)
            return web.json_response({"ok": True})

        # Download attached files
        attachments: list[Attachment] = []
        if file_infos:
            bot_token = request.app[bot_token_key]
            session = request.app[bot_session_key]
            dest_dir = request.app.get(media_dir_key, "") or store.media_dir()
            for fi in file_infos:
                try:
                    local_path = await download_telegram_file(
                        session, bot_token, fi["file_id"], dest_dir
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
            await _reply(
                request,
                request.app[bot_token_key],
                sender,
                "Sorry, something went wrong. Please try again.",
            )
        finally:
            current_chat_id.reset(token)

        return web.json_response({"ok": True})

    return web.post("/webhook/telegram/{secret}", handler)
