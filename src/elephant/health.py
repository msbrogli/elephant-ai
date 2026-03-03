"""Health check HTTP server using aiohttp."""

from __future__ import annotations

import logging
from collections.abc import Awaitable, Callable, Mapping
from typing import TYPE_CHECKING

import aiohttp
from aiohttp import web

from elephant.web.traces import register_routes as register_trace_routes
from elephant.webhooks.telegram import bot_session_key, bot_token_key, create_telegram_webhook
from elephant.webhooks.twilio import create_twilio_webhook

if TYPE_CHECKING:
    from elephant.config import AppConfig
    from elephant.messaging.base import IncomingMessage
    from elephant.router import ChatRouter

logger = logging.getLogger(__name__)

FlowCallback = Callable[[], Awaitable[object]]

flows_key: web.AppKey[dict[str, FlowCallback]] = web.AppKey(
    "flows", dict
)


async def _health_handler(request: web.Request) -> web.Response:
    return web.json_response({"status": "ok", "service": "my-little-elephant"})


async def _run_flow_handler(request: web.Request) -> web.Response:
    """Run a named flow on demand."""
    flow_name = request.match_info["flow_name"]
    registered = request.app.get(flows_key, {})

    if flow_name not in registered:
        return web.json_response(
            {
                "error": f"unknown flow: {flow_name}",
                "available": sorted(registered),
            },
            status=404,
        )

    try:
        result = await registered[flow_name]()
        logger.info("Flow %s triggered via API (result=%s)", flow_name, result)
        return web.json_response({"flow": flow_name, "result": result})
    except Exception:
        logger.exception("Flow %s failed via API", flow_name)
        return web.json_response(
            {"error": f"flow {flow_name} failed"},
            status=500,
        )


def create_app(
    config: AppConfig | None = None,
    router: ChatRouter | None = None,
    flows: Mapping[str, FlowCallback] | None = None,
) -> web.Application:
    """Create the aiohttp application with health endpoint and optional webhooks."""
    app = web.Application()
    app.router.add_get("/health", _health_handler)

    if flows:
        app[flows_key] = dict(flows)
        app.router.add_post("/api/run/{flow_name}", _run_flow_handler)

    if router is not None:
        register_trace_routes(app, router)

    if config is not None and router is not None:
        provider = config.messaging.provider
        if provider == "twilio":
            # For twilio, we still need an on_message — route via first db
            dbs = router.get_all_databases()
            if dbs:
                first_db = dbs[0]

                async def twilio_on_message(msg: IncomingMessage) -> None:
                    await first_db.anytime.handle_message(msg)

                route = create_twilio_webhook(
                    config.messaging.twilio.auth_token,
                    twilio_on_message,
                )
                app.router.add_route(route.method, route.path, route.handler)
        elif (
            provider == "telegram"
            and config.messaging.telegram.mode != "polling"
        ):
            route = create_telegram_webhook(
                config.messaging.telegram.webhook_secret,
                router,
            )
            app.router.add_route(route.method, route.path, route.handler)
            # Store bot_token on app for webhook reply helper
            app[bot_token_key] = config.messaging.telegram.bot_token

            async def _on_startup(app: web.Application) -> None:
                app[bot_session_key] = aiohttp.ClientSession()

            async def _on_cleanup(app: web.Application) -> None:
                await app[bot_session_key].close()

            app.on_startup.append(_on_startup)
            app.on_cleanup.append(_on_cleanup)

    return app
