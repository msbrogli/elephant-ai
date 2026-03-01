"""Tests for brain context enrichment: preferences/people updates."""

from unittest.mock import AsyncMock, MagicMock

from elephant.brain.context_enrichment import process_context_update
from elephant.data.store import DataStore
from elephant.git_ops import GitRepo
from elephant.llm.client import LLMResponse


class TestProcessContextUpdate:
    async def test_adds_location(self, data_dir):
        store = DataStore(data_dir)
        store.initialize()
        git = MagicMock(spec=GitRepo)
        git.auto_commit = MagicMock(return_value="abc123")

        llm = AsyncMock()
        llm.chat = AsyncMock(
            return_value=LLMResponse(
                content="location:\n  name: Grandma's house\n  description: 456 Oak St",
                model="m",
                usage={},
            )
        )

        result = await process_context_update("Grandma lives at 456 Oak St", llm, "m", store, git)

        assert result is True
        prefs = store.read_preferences()
        assert "Grandma's house" in prefs.locations
        assert prefs.locations["Grandma's house"] == "456 Oak St"

    async def test_adds_note(self, data_dir):
        store = DataStore(data_dir)
        store.initialize()
        git = MagicMock(spec=GitRepo)
        git.auto_commit = MagicMock(return_value="abc123")

        llm = AsyncMock()
        llm.chat = AsyncMock(
            return_value=LLMResponse(
                content="note: Dad loves coffee",
                model="m",
                usage={},
            )
        )

        result = await process_context_update("I love coffee", llm, "m", store, git)

        assert result is True
        prefs = store.read_preferences()
        assert len(prefs.notes) == 1
        assert prefs.notes[0] == "Dad loves coffee"

    async def test_adds_multiple_notes(self, data_dir):
        store = DataStore(data_dir)
        store.initialize()
        git = MagicMock(spec=GitRepo)
        git.auto_commit = MagicMock(return_value="abc123")

        llm = AsyncMock()
        llm.chat = AsyncMock(
            return_value=LLMResponse(
                content=(
                    "notes:\n"
                    "  - Dad loves coffee\n"
                    "  - Mom prefers tea\n"
                ),
                model="m",
                usage={},
            )
        )

        result = await process_context_update("I love coffee, wife loves tea", llm, "m", store, git)

        assert result is True
        prefs = store.read_preferences()
        assert len(prefs.notes) == 2
        assert prefs.notes[0] == "Dad loves coffee"
        assert prefs.notes[1] == "Mom prefers tea"

    async def test_updates_person(self, data_dir):
        from elephant.data.models import Person

        store = DataStore(data_dir)
        store.initialize()

        # Create an existing person
        store.write_person(
            Person(person_id="lily", display_name="Lily", relationship="daughter"),
        )

        git = MagicMock(spec=GitRepo)
        git.auto_commit = MagicMock(return_value="abc123")

        llm = AsyncMock()
        llm.chat = AsyncMock(
            return_value=LLMResponse(
                content="person_update:\n  name: Lily\n  field: close_friend\n  value: true",
                model="m",
                usage={},
            )
        )

        result = await process_context_update("Lily is my closest", llm, "m", store, git)

        assert result is True
        person = store.read_person("lily")
        assert person is not None
        assert person.close_friend is True

    async def test_mixed_location_and_note(self, data_dir):
        store = DataStore(data_dir)
        store.initialize()
        git = MagicMock(spec=GitRepo)
        git.auto_commit = MagicMock(return_value="abc123")

        llm = AsyncMock()
        llm.chat = AsyncMock(
            return_value=LLMResponse(
                content=(
                    "location:\n  name: Home\n  description: 123 Main St\n"
                    "note: Lily's favorite color is purple\n"
                ),
                model="m",
                usage={},
            )
        )

        result = await process_context_update(
            "We live at 123 Main, Lily loves purple", llm, "m", store, git
        )

        assert result is True
        prefs = store.read_preferences()
        assert "Home" in prefs.locations
        assert prefs.notes[0] == "Lily's favorite color is purple"

    async def test_invalid_llm_response(self, data_dir):
        store = DataStore(data_dir)
        store.initialize()
        git = MagicMock(spec=GitRepo)

        llm = AsyncMock()
        llm.chat = AsyncMock(
            return_value=LLMResponse(content="just a string", model="m", usage={})
        )

        result = await process_context_update("test", llm, "m", store, git)
        assert result is False

    async def test_yaml_parse_error(self, data_dir):
        store = DataStore(data_dir)
        store.initialize()
        git = MagicMock(spec=GitRepo)

        llm = AsyncMock()
        llm.chat = AsyncMock(
            return_value=LLMResponse(content=": invalid: yaml: [", model="m", usage={})
        )

        result = await process_context_update("test", llm, "m", store, git)
        assert result is False
