"""Tests for Twilio webhook: HMAC validation, message parsing."""

import base64
import hashlib
import hmac

from aiohttp import web
from aiohttp.test_utils import AioHTTPTestCase

from elephant.messaging.base import IncomingMessage
from elephant.webhooks.twilio import create_twilio_webhook, validate_twilio_signature


class TestTwilioSignatureValidation:
    def test_valid_signature(self):
        auth_token = "test_token"
        url = "https://example.com/webhook/twilio"
        params = {"Body": "Hello", "From": "whatsapp:+1234"}
        # Compute expected signature
        sorted_params = sorted(params.items())
        data = url + "".join(f"{k}{v}" for k, v in sorted_params)
        expected = base64.b64encode(
            hmac.new(auth_token.encode(), data.encode(), hashlib.sha1).digest()
        ).decode()

        assert validate_twilio_signature(auth_token, url, params, expected) is True

    def test_invalid_signature(self):
        assert validate_twilio_signature("token", "url", {}, "bad_sig") is False


class TestTwilioWebhook(AioHTTPTestCase):
    async def get_application(self) -> web.Application:
        self.received_messages: list[IncomingMessage] = []

        async def on_message(msg: IncomingMessage) -> None:
            self.received_messages.append(msg)

        app = web.Application()
        route = create_twilio_webhook("", on_message)  # empty auth_token = skip validation
        app.router.add_route(route.method, route.path, route.handler)
        return app

    async def test_valid_message(self):
        resp = await self.client.post(
            "/webhook/twilio",
            data="Body=Hello+world&From=whatsapp%3A%2B1234&MessageSid=SM123",
            headers={"Content-Type": "application/x-www-form-urlencoded"},
        )
        assert resp.status == 200
        assert len(self.received_messages) == 1
        assert self.received_messages[0].text == "Hello world"
        assert self.received_messages[0].sender == "whatsapp:+1234"

    async def test_empty_body(self):
        resp = await self.client.post(
            "/webhook/twilio",
            data="Body=&From=whatsapp%3A%2B1234&MessageSid=SM123",
            headers={"Content-Type": "application/x-www-form-urlencoded"},
        )
        assert resp.status == 200
        assert len(self.received_messages) == 0

    async def test_returns_twiml(self):
        resp = await self.client.post(
            "/webhook/twilio",
            data="Body=Hi&From=whatsapp%3A%2B1234&MessageSid=SM123",
            headers={"Content-Type": "application/x-www-form-urlencoded"},
        )
        text = await resp.text()
        assert "<Response>" in text


class TestTwilioWebhookWithAuth(AioHTTPTestCase):
    async def get_application(self) -> web.Application:
        self.auth_token = "test_secret_token"

        async def on_message(msg: IncomingMessage) -> None:
            pass

        app = web.Application()
        route = create_twilio_webhook(self.auth_token, on_message)
        app.router.add_route(route.method, route.path, route.handler)
        return app

    async def test_invalid_signature_returns_403(self):
        resp = await self.client.post(
            "/webhook/twilio",
            data="Body=Hello&From=test&MessageSid=SM1",
            headers={
                "Content-Type": "application/x-www-form-urlencoded",
                "X-Twilio-Signature": "invalid_sig",
            },
        )
        assert resp.status == 403
