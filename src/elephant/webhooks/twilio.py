"""Twilio webhook handler with HMAC-SHA1 validation."""

import hashlib
import hmac
import logging
from collections.abc import Awaitable, Callable
from datetime import UTC, datetime

from aiohttp import web

from elephant.messaging.base import IncomingMessage

logger = logging.getLogger(__name__)

OnMessageCallback = Callable[[IncomingMessage], Awaitable[None]]


def validate_twilio_signature(
    auth_token: str,
    url: str,
    params: dict[str, str],
    signature: str,
) -> bool:
    """Validate Twilio HMAC-SHA1 request signature."""
    # Sort params and append to URL
    sorted_params = sorted(params.items())
    data = url + "".join(f"{k}{v}" for k, v in sorted_params)
    expected = hmac.new(
        auth_token.encode("utf-8"),
        data.encode("utf-8"),
        hashlib.sha1,
    ).digest()
    import base64

    expected_b64 = base64.b64encode(expected).decode("utf-8")
    return hmac.compare_digest(expected_b64, signature)


def create_twilio_webhook(
    auth_token: str,
    on_message: OnMessageCallback,
) -> web.RouteDef:
    """Create the Twilio webhook route."""

    async def handler(request: web.Request) -> web.Response:
        # Parse form data
        data = await request.post()
        params = {k: str(v) for k, v in data.items()}

        # Validate signature
        signature = request.headers.get("X-Twilio-Signature", "")
        url = str(request.url)
        if auth_token and not validate_twilio_signature(auth_token, url, params, signature):
            logger.warning("Invalid Twilio signature")
            return web.Response(status=403, text="Invalid signature")

        # Parse incoming message
        body = params.get("Body", "")
        sender = params.get("From", "")
        message_id = params.get("MessageSid", "")

        if not body:
            return web.Response(status=200, text="<Response></Response>", content_type="text/xml")

        message = IncomingMessage(
            text=body,
            sender=sender,
            message_id=message_id,
            timestamp=datetime.now(UTC),
        )

        try:
            await on_message(message)
        except Exception:
            logger.exception("Error handling Twilio message")

        return web.Response(status=200, text="<Response></Response>", content_type="text/xml")

    return web.post("/webhook/twilio", handler)
