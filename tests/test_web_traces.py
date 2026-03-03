"""Tests for web trace API endpoints."""

from dataclasses import dataclass, field
from unittest.mock import MagicMock

from aiohttp import web
from aiohttp.test_utils import AioHTTPTestCase

from elephant.data.store import DataStore
from elephant.tracing import IntentStep, LLMCallStep, Trace
from elephant.web.traces import register_routes


@dataclass
class FakeDatabase:
    name: str
    store: DataStore
    auth_secret: str = "secret"
    git: object = field(default_factory=MagicMock)
    messaging: object = field(default_factory=MagicMock)
    anytime: object = field(default_factory=MagicMock)
    morning: object = field(default_factory=MagicMock)
    evening: object = field(default_factory=MagicMock)
    question_mgr: object = field(default_factory=MagicMock)
    schedule: object = field(default_factory=MagicMock)


class TestTraceAPI(AioHTTPTestCase):
    async def get_application(self) -> web.Application:
        self.store = DataStore(str(self.tmp_path))
        self.store.initialize()

        db = FakeDatabase(name="family", store=self.store)
        self.router = MagicMock()
        self.router.get_all_databases.return_value = [db]

        app = web.Application()
        register_routes(app, self.router)
        return app

    def setUp(self):
        import tempfile
        self.tmp_dir = tempfile.TemporaryDirectory()
        self.tmp_path = self.tmp_dir.name
        super().setUp()

    def tearDown(self):
        super().tearDown()
        self.tmp_dir.cleanup()

    async def test_databases_list(self):
        resp = await self.client.get("/api/traces/databases")
        assert resp.status == 200
        data = await resp.json()
        assert data["databases"] == [{"name": "family"}]

    async def test_traces_list_empty(self):
        resp = await self.client.get("/api/traces/family")
        assert resp.status == 200
        data = await resp.json()
        assert data["traces"] == []
        assert data["total"] == 0

    async def test_traces_list_with_data(self):
        trace = Trace(
            database_name="family",
            message_id="msg-1",
            sender="alice",
            message_text="hello world",
            intent="NEW_MEMORY",
            steps=[IntentStep(resolved_intent="NEW_MEMORY")],
        )
        self.store.append_trace(trace)

        resp = await self.client.get("/api/traces/family")
        assert resp.status == 200
        data = await resp.json()
        assert data["total"] == 1
        assert len(data["traces"]) == 1
        summary = data["traces"][0]
        assert summary["trace_id"] == trace.trace_id
        assert summary["intent"] == "NEW_MEMORY"
        assert summary["step_counts"]["intent"] == 1

    async def test_trace_detail(self):
        trace = Trace(
            database_name="family",
            message_id="msg-2",
            sender="bob",
            message_text="park visit",
            intent="NEW_MEMORY",
            final_response="Got it!",
            steps=[
                IntentStep(resolved_intent="NEW_MEMORY"),
                LLMCallStep(method="chat_with_tools", model="gpt-4"),
            ],
        )
        self.store.append_trace(trace)

        resp = await self.client.get(f"/api/traces/family/{trace.trace_id}")
        assert resp.status == 200
        data = await resp.json()
        assert data["trace_id"] == trace.trace_id
        assert data["final_response"] == "Got it!"
        assert len(data["steps"]) == 2

    async def test_trace_detail_not_found(self):
        resp = await self.client.get("/api/traces/family/nonexistent")
        assert resp.status == 404
        data = await resp.json()
        assert "not found" in data["error"]

    async def test_unknown_database_404(self):
        resp = await self.client.get("/api/traces/nonexistent")
        assert resp.status == 404
        data = await resp.json()
        assert "unknown database" in data["error"]

    async def test_traces_pagination(self):
        for i in range(5):
            trace = Trace(
                database_name="family",
                message_id=f"msg-{i}",
                sender="alice",
                message_text=f"message {i}",
            )
            self.store.append_trace(trace)

        resp = await self.client.get("/api/traces/family?page=0&per_page=2")
        data = await resp.json()
        assert data["total"] == 5
        assert len(data["traces"]) == 2

        resp = await self.client.get("/api/traces/family?page=2&per_page=2")
        data = await resp.json()
        assert len(data["traces"]) == 1  # Last page

    async def test_spa_catch_all(self):
        resp = await self.client.get("/traces/")
        # Returns 200 if frontend/dist/index.html exists, 404 otherwise
        assert resp.status in (200, 404)
