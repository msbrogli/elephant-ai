"""Tests for the people API endpoint."""

from dataclasses import dataclass, field
from datetime import date
from unittest.mock import MagicMock

from aiohttp import web
from aiohttp.test_utils import AioHTTPTestCase

from elephant.data.models import CurrentThread, Person, PersonRelationship
from elephant.data.store import DataStore
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


class TestPeopleAPI(AioHTTPTestCase):
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

    async def test_people_empty(self):
        resp = await self.client.get("/api/people/family")
        assert resp.status == 200
        data = await resp.json()
        assert data["people"] == []

    async def test_people_with_data(self):
        p1 = Person(
            person_id="alice",
            display_name="Alice",
            relationship=["sister"],
            groups=["close-friends"],
            relationships=[PersonRelationship(person_id="bob", label="sibling")],
        )
        p2 = Person(
            person_id="bob",
            display_name="Bob",
            relationship=["brother"],
            relationships=[PersonRelationship(person_id="alice", label="sibling")],
        )
        self.store.write_person(p1)
        self.store.write_person(p2)

        resp = await self.client.get("/api/people/family")
        assert resp.status == 200
        data = await resp.json()
        assert len(data["people"]) == 2

        names = {p["display_name"] for p in data["people"]}
        assert names == {"Alice", "Bob"}

        alice = next(p for p in data["people"] if p["person_id"] == "alice")
        assert alice["relationship"] == ["sister"]
        assert alice["groups"] == ["close-friends"]
        assert len(alice["relationships"]) == 1
        assert alice["relationships"][0]["label"] == "sibling"

    async def test_people_with_threads(self):
        p = Person(
            person_id="carol",
            display_name="Carol",
            relationship=["friend"],
            current_threads=[
                CurrentThread(
                    topic="House hunting",
                    latest_update="Found a nice place",
                    last_mentioned_date=date(2026, 3, 1),
                ),
            ],
        )
        self.store.write_person(p)

        resp = await self.client.get("/api/people/family")
        assert resp.status == 200
        data = await resp.json()
        assert len(data["people"]) == 1

        carol = data["people"][0]
        assert len(carol["current_threads"]) == 1
        assert carol["current_threads"][0]["topic"] == "House hunting"

    async def test_people_unknown_database(self):
        resp = await self.client.get("/api/people/nonexistent")
        assert resp.status == 404
        data = await resp.json()
        assert "unknown database" in data["error"]
