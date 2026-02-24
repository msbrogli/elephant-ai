"""Tests for tool executor: each handler with mocked DataStore."""

import json
from datetime import date
from unittest.mock import AsyncMock, MagicMock

import pytest

from elephant.data.models import Event, Person
from elephant.data.store import DataStore
from elephant.git_ops import GitRepo
from elephant.llm.client import LLMResponse, ToolCall
from elephant.tools.executor import ToolExecutor


@pytest.fixture
def executor(data_dir):
    store = DataStore(data_dir)
    store.initialize()
    git = MagicMock(spec=GitRepo)
    git.auto_commit = MagicMock(return_value="abc123")
    llm = AsyncMock()
    return ToolExecutor(store, git, llm, "test-model"), store, git, llm


class TestListEvents:
    async def test_empty_store(self, executor):
        ex, store, git, llm = executor
        tc = ToolCall(id="1", function_name="list_events", arguments="{}")
        result = json.loads(await ex.execute(tc))
        assert result["count"] == 0
        assert result["events"] == []

    async def test_with_events(self, executor):
        ex, store, git, llm = executor
        event = Event(
            id="20260224_park_day",
            date=date(2026, 2, 24),
            title="Park day",
            type="daily",
            description="Went to the park",
            people=["Lily"],
            source="agent",
        )
        store.write_event(event)

        tc = ToolCall(id="1", function_name="list_events", arguments="{}")
        result = json.loads(await ex.execute(tc))
        assert result["count"] == 1
        assert result["events"][0]["title"] == "Park day"

    async def test_filter_by_people(self, executor):
        ex, store, git, llm = executor
        store.write_event(Event(
            id="20260224_park", date=date(2026, 2, 24), title="Park",
            type="daily", description="Park", people=["Lily"], source="agent",
        ))
        store.write_event(Event(
            id="20260224_work", date=date(2026, 2, 24), title="Work",
            type="daily", description="Work", people=["Dad"], source="agent",
        ))

        tc = ToolCall(
            id="1", function_name="list_events",
            arguments=json.dumps({"people": ["Lily"]}),
        )
        result = json.loads(await ex.execute(tc))
        assert result["count"] == 1
        assert result["events"][0]["title"] == "Park"


class TestGetEvent:
    async def test_found(self, executor):
        ex, store, git, llm = executor
        store.write_event(Event(
            id="20260224_park_day", date=date(2026, 2, 24), title="Park day",
            type="daily", description="Fun", people=["Lily"], source="agent",
        ))

        tc = ToolCall(
            id="1", function_name="get_event",
            arguments=json.dumps({"event_id": "20260224_park_day"}),
        )
        result = json.loads(await ex.execute(tc))
        assert result["title"] == "Park day"

    async def test_not_found(self, executor):
        ex, store, git, llm = executor
        tc = ToolCall(
            id="1", function_name="get_event",
            arguments=json.dumps({"event_id": "20260224_nope"}),
        )
        result = json.loads(await ex.execute(tc))
        assert "error" in result


class TestCreateEvent:
    async def test_creates_and_commits(self, executor):
        ex, store, git, llm = executor
        tc = ToolCall(
            id="1", function_name="create_event",
            arguments=json.dumps({
                "title": "Park day",
                "date": "2026-02-24",
                "type": "daily",
                "description": "Went to the park with Lily",
                "people": ["Lily"],
            }),
        )
        result = json.loads(await ex.execute(tc))
        assert "created" in result
        assert result["title"] == "Park day"
        git.auto_commit.assert_called_once()

        # Verify stored
        event = store.find_event_by_id(result["created"])
        assert event is not None
        assert event.title == "Park day"


class TestUpdateEvent:
    async def test_updates_existing(self, executor):
        ex, store, git, llm = executor
        store.write_event(Event(
            id="20260224_park_day", date=date(2026, 2, 24), title="Park day",
            type="daily", description="Fun", people=["Lily"], source="agent",
        ))

        tc = ToolCall(
            id="1", function_name="update_event",
            arguments=json.dumps({
                "event_id": "20260224_park_day",
                "description": "Had a great time at the park!",
            }),
        )
        result = json.loads(await ex.execute(tc))
        assert result["updated"] == "20260224_park_day"

        event = store.find_event_by_id("20260224_park_day")
        assert event is not None
        assert event.description == "Had a great time at the park!"


class TestDeleteEvent:
    async def test_deletes_existing(self, executor):
        ex, store, git, llm = executor
        store.write_event(Event(
            id="20260224_park_day", date=date(2026, 2, 24), title="Park day",
            type="daily", description="Fun", people=["Lily"], source="agent",
        ))

        tc = ToolCall(
            id="1", function_name="delete_event",
            arguments=json.dumps({"event_id": "20260224_park_day"}),
        )
        result = json.loads(await ex.execute(tc))
        assert result["deleted"] == "20260224_park_day"
        assert store.find_event_by_id("20260224_park_day") is None

    async def test_not_found(self, executor):
        ex, store, git, llm = executor
        tc = ToolCall(
            id="1", function_name="delete_event",
            arguments=json.dumps({"event_id": "20260224_nope"}),
        )
        result = json.loads(await ex.execute(tc))
        assert "error" in result


class TestContextTools:
    async def test_get_context(self, executor):
        ex, store, git, llm = executor
        store.write_context({"notes": ["test"]})

        tc = ToolCall(id="1", function_name="get_context", arguments="{}")
        result = json.loads(await ex.execute(tc))
        assert result["notes"] == ["test"]

    async def test_update_context(self, executor):
        ex, store, git, llm = executor
        tc = ToolCall(
            id="1", function_name="update_context",
            arguments=json.dumps({
                "family_members": [{"name": "Lily", "role": "daughter"}],
                "notes": ["She loves dinosaurs"],
            }),
        )
        result = json.loads(await ex.execute(tc))
        assert result["updated"] is True

        ctx = store.read_context()
        assert ctx["family"]["members"][0]["name"] == "Lily"
        assert any("dinosaurs" in n["text"] for n in ctx["notes"])


class TestListPeople:
    async def test_empty(self, executor):
        ex, store, git, llm = executor
        tc = ToolCall(id="1", function_name="list_people", arguments="{}")
        result = json.loads(await ex.execute(tc))
        assert result["people"] == []

    async def test_with_people(self, executor):
        ex, store, git, llm = executor
        store.write_person(
            Person(person_id="lily", display_name="Lily", relationship="daughter"),
        )

        tc = ToolCall(id="1", function_name="list_people", arguments="{}")
        result = json.loads(await ex.execute(tc))
        assert len(result["people"]) == 1
        assert result["people"][0]["display_name"] == "Lily"
        assert result["people"][0]["close_friend"] is False
        assert result["people"][0]["last_contact"] is None


class TestUpdatePerson:
    async def test_updates_existing(self, executor):
        ex, store, git, llm = executor
        store.write_person(
            Person(person_id="lily", display_name="Lily", relationship="daughter"),
        )

        tc = ToolCall(
            id="1", function_name="update_person",
            arguments=json.dumps({
                "person_id": "lily",
                "close_friend": True,
                "birthday": "2023-01-10",
            }),
        )
        result = json.loads(await ex.execute(tc))
        assert result["updated"] == "lily"

        person = store.read_person("lily")
        assert person is not None
        assert person.close_friend is True
        assert person.birthday is not None

    async def test_not_found(self, executor):
        ex, store, git, llm = executor
        tc = ToolCall(
            id="1", function_name="update_person",
            arguments=json.dumps({"person_id": "nope"}),
        )
        result = json.loads(await ex.execute(tc))
        assert "error" in result


class TestLastContactAutoUpdate:
    async def test_updates_last_contact_on_event_create(self, executor):
        ex, store, git, llm = executor
        store.write_person(
            Person(person_id="lily", display_name="Lily", relationship="daughter"),
        )

        tc = ToolCall(
            id="1", function_name="create_event",
            arguments=json.dumps({
                "title": "Park day",
                "date": "2026-02-24",
                "type": "daily",
                "description": "Park",
                "people": ["Lily"],
            }),
        )
        await ex.execute(tc)

        person = store.read_person("lily")
        assert person is not None
        assert person.last_contact is not None
        assert str(person.last_contact) == "2026-02-24"

    async def test_does_not_backdate_last_contact(self, executor):
        from datetime import date
        ex, store, git, llm = executor
        store.write_person(
            Person(
                person_id="lily", display_name="Lily",
                relationship="daughter", last_contact=date(2026, 2, 25),
            ),
        )

        tc = ToolCall(
            id="1", function_name="create_event",
            arguments=json.dumps({
                "title": "Old event",
                "date": "2026-02-20",
                "type": "daily",
                "description": "Historical",
                "people": ["Lily"],
            }),
        )
        await ex.execute(tc)

        person = store.read_person("lily")
        assert person is not None
        assert str(person.last_contact) == "2026-02-25"  # Not backdated


class TestDescribeAttachment:
    async def test_image_returns_description(self, executor, tmp_path):
        ex, store, git, llm = executor
        # Create a fake image file
        img = tmp_path / "photo.jpg"
        img.write_bytes(b"\xff\xd8\xff\xe0fake-jpeg-data")

        llm.chat = AsyncMock(return_value=LLMResponse(
            content="A family photo at the park.", model="m", usage={},
        ))

        tc = ToolCall(
            id="1", function_name="describe_attachment",
            arguments=json.dumps({"file_path": str(img)}),
        )
        result = json.loads(await ex.execute(tc))
        assert "description" in result
        assert "park" in result["description"].lower()
        llm.chat.assert_called_once()

    async def test_text_file_returns_contents(self, executor, tmp_path):
        ex, store, git, llm = executor
        doc = tmp_path / "notes.txt"
        doc.write_text("Hello, this is a test document.")

        tc = ToolCall(
            id="1", function_name="describe_attachment",
            arguments=json.dumps({"file_path": str(doc)}),
        )
        result = json.loads(await ex.execute(tc))
        assert result["file_type"] == "txt"
        assert "test document" in result["contents"]

    async def test_missing_file_returns_error(self, executor):
        ex, store, git, llm = executor
        tc = ToolCall(
            id="1", function_name="describe_attachment",
            arguments=json.dumps({"file_path": "/nonexistent/file.jpg"}),
        )
        result = json.loads(await ex.execute(tc))
        assert "error" in result
        assert "not found" in result["error"].lower()

    async def test_large_file_truncated(self, executor, tmp_path):
        ex, store, git, llm = executor
        doc = tmp_path / "big.csv"
        doc.write_text("x" * 200_000)

        tc = ToolCall(
            id="1", function_name="describe_attachment",
            arguments=json.dumps({"file_path": str(doc)}),
        )
        result = json.loads(await ex.execute(tc))
        assert result["file_type"] == "csv"
        assert len(result["contents"]) == 100_000

    async def test_json_file_returns_contents(self, executor, tmp_path):
        ex, store, git, llm = executor
        doc = tmp_path / "data.json"
        doc.write_text('{"key": "value"}')

        tc = ToolCall(
            id="1", function_name="describe_attachment",
            arguments=json.dumps({"file_path": str(doc)}),
        )
        result = json.loads(await ex.execute(tc))
        assert result["file_type"] == "json"
        assert '"key"' in result["contents"]

    async def test_png_uses_vision(self, executor, tmp_path):
        ex, store, git, llm = executor
        img = tmp_path / "screenshot.png"
        img.write_bytes(b"\x89PNG\r\n\x1a\nfake-png-data")

        llm.chat = AsyncMock(return_value=LLMResponse(
            content="A screenshot of a chat.", model="m", usage={},
        ))

        tc = ToolCall(
            id="1", function_name="describe_attachment",
            arguments=json.dumps({"file_path": str(img)}),
        )
        result = json.loads(await ex.execute(tc))
        assert "description" in result
        llm.chat.assert_called_once()


class TestUnknownTool:
    async def test_returns_error(self, executor):
        ex, store, git, llm = executor
        tc = ToolCall(id="1", function_name="does_not_exist", arguments="{}")
        result = json.loads(await ex.execute(tc))
        assert "error" in result
        assert "Unknown tool" in result["error"]
