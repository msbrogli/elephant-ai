"""Tests for health server."""

from unittest.mock import AsyncMock

from aiohttp import web
from aiohttp.test_utils import AioHTTPTestCase

from elephant.health import create_app


class TestHealthEndpoint(AioHTTPTestCase):
    async def get_application(self) -> web.Application:
        return create_app()

    async def test_health_returns_ok(self):
        resp = await self.client.get("/health")
        assert resp.status == 200
        data = await resp.json()
        assert data["status"] == "ok"
        assert data["service"] == "my-little-elephant"

    async def test_health_content_type(self):
        resp = await self.client.get("/health")
        assert "application/json" in resp.headers["Content-Type"]

    async def test_unknown_route_returns_404(self):
        resp = await self.client.get("/unknown")
        assert resp.status == 404


class TestRunFlowEndpoint(AioHTTPTestCase):
    async def get_application(self) -> web.Application:
        self.mock_morning = AsyncMock(return_value=True)
        self.mock_evening = AsyncMock(return_value=True)
        flows = {
            "morning_digest": self.mock_morning,
            "evening_checkin": self.mock_evening,
        }
        return create_app(flows=flows)

    async def test_run_flow_success(self):
        resp = await self.client.post("/api/run/morning_digest")
        assert resp.status == 200
        data = await resp.json()
        assert data["flow"] == "morning_digest"
        assert data["result"] is True
        self.mock_morning.assert_awaited_once()

    async def test_run_flow_returns_result(self):
        self.mock_evening.return_value = False
        resp = await self.client.post("/api/run/evening_checkin")
        assert resp.status == 200
        data = await resp.json()
        assert data["result"] is False

    async def test_run_unknown_flow_404(self):
        resp = await self.client.post("/api/run/nonexistent")
        assert resp.status == 404
        data = await resp.json()
        assert "unknown flow" in data["error"]
        assert "morning_digest" in data["available"]

    async def test_run_flow_exception_500(self):
        self.mock_morning.side_effect = RuntimeError("boom")
        resp = await self.client.post("/api/run/morning_digest")
        assert resp.status == 500
        data = await resp.json()
        assert "failed" in data["error"]

    async def test_no_flows_no_route(self):
        """When no flows are registered, the route should not exist."""
        app = create_app()
        from aiohttp.test_utils import TestClient, TestServer

        async with TestClient(TestServer(app)) as client:
            resp = await client.post("/api/run/morning_digest")
            assert resp.status == 404
