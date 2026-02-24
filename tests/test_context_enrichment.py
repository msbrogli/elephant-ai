"""Tests for brain context enrichment: context/people updates."""

from unittest.mock import AsyncMock, MagicMock

from elephant.brain.context_enrichment import process_context_update
from elephant.data.store import DataStore
from elephant.git_ops import GitRepo
from elephant.llm.client import LLMResponse


class TestProcessContextUpdate:
    async def test_adds_family_member(self, data_dir):
        store = DataStore(data_dir)
        store.initialize()
        git = MagicMock(spec=GitRepo)
        git.auto_commit = MagicMock(return_value="abc123")

        llm = AsyncMock()
        llm.chat = AsyncMock(
            return_value=LLMResponse(
                content="family_member:\n  name: Lily\n  role: daughter\n  birthday: 2023-01-10",
                model="m",
                usage={},
            )
        )

        result = await process_context_update(
            "My daughter Lily was born on Jan 10 2023",
            llm, "m", store, git,
        )

        assert result is True
        ctx = store.read_context()
        assert len(ctx["family"]["members"]) == 1
        assert ctx["family"]["members"][0]["name"] == "Lily"
        git.auto_commit.assert_called_once()

    async def test_adds_friend(self, data_dir):
        store = DataStore(data_dir)
        store.initialize()
        git = MagicMock(spec=GitRepo)
        git.auto_commit = MagicMock(return_value="abc123")

        llm = AsyncMock()
        llm.chat = AsyncMock(
            return_value=LLMResponse(
                content="friend:\n  name: Rafael\n  relationship: college friend",
                model="m",
                usage={},
            )
        )

        result = await process_context_update("Rafael is my college friend", llm, "m", store, git)

        assert result is True
        ctx = store.read_context()
        assert len(ctx["friends"]) == 1
        assert ctx["friends"][0]["name"] == "Rafael"

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
        ctx = store.read_context()
        assert "Grandma's house" in ctx["locations"]

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
        ctx = store.read_context()
        assert len(ctx["notes"]) == 1
        assert ctx["notes"][0]["text"] == "Dad loves coffee"
        assert ctx["notes"][0]["date"]  # should have a date stamp

    async def test_adds_multiple_family_members(self, data_dir):
        store = DataStore(data_dir)
        store.initialize()
        git = MagicMock(spec=GitRepo)
        git.auto_commit = MagicMock(return_value="abc123")

        llm = AsyncMock()
        llm.chat = AsyncMock(
            return_value=LLMResponse(
                content=(
                    "family_members:\n"
                    "  - name: Daniel\n"
                    "    role: father\n"
                    "  - name: Hannah\n"
                    "    role: mother\n"
                    "  - name: Oliver\n"
                    "    role: son\n"
                ),
                model="m",
                usage={},
            )
        )

        result = await process_context_update(
            "My name is Daniel, my wife Hannah, son Oliver",
            llm, "m", store, git,
        )

        assert result is True
        ctx = store.read_context()
        names = [m["name"] for m in ctx["family"]["members"]]
        assert names == ["Daniel", "Hannah", "Oliver"]
        git.auto_commit.assert_called_once()

    async def test_adds_family_member_list_singular_key(self, data_dir):
        """LLM returns a list under the singular key 'family_member'."""
        store = DataStore(data_dir)
        store.initialize()
        git = MagicMock(spec=GitRepo)
        git.auto_commit = MagicMock(return_value="abc123")

        llm = AsyncMock()
        llm.chat = AsyncMock(
            return_value=LLMResponse(
                content=(
                    "family_member:\n"
                    "  - name: Alice\n"
                    "    role: daughter\n"
                    "  - name: Bob\n"
                    "    role: son\n"
                ),
                model="m",
                usage={},
            )
        )

        result = await process_context_update("Alice and Bob are my kids", llm, "m", store, git)

        assert result is True
        ctx = store.read_context()
        assert len(ctx["family"]["members"]) == 2

    async def test_adds_multiple_friends(self, data_dir):
        store = DataStore(data_dir)
        store.initialize()
        git = MagicMock(spec=GitRepo)
        git.auto_commit = MagicMock(return_value="abc123")

        llm = AsyncMock()
        llm.chat = AsyncMock(
            return_value=LLMResponse(
                content=(
                    "friends:\n"
                    "  - name: Rafael\n"
                    "    relationship: college friend\n"
                    "  - name: Sarah\n"
                    "    relationship: neighbor\n"
                ),
                model="m",
                usage={},
            )
        )

        result = await process_context_update("Rafael and Sarah are friends", llm, "m", store, git)

        assert result is True
        ctx = store.read_context()
        assert len(ctx["friends"]) == 2
        assert ctx["friends"][0]["name"] == "Rafael"
        assert ctx["friends"][1]["name"] == "Sarah"

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
        ctx = store.read_context()
        assert len(ctx["notes"]) == 2
        assert ctx["notes"][0]["text"] == "Dad loves coffee"
        assert ctx["notes"][1]["text"] == "Mom prefers tea"
        assert all(n["date"] for n in ctx["notes"])

    async def test_mixed_singular_and_plural(self, data_dir):
        """LLM returns a mix of family members and a note in one response."""
        store = DataStore(data_dir)
        store.initialize()
        git = MagicMock(spec=GitRepo)
        git.auto_commit = MagicMock(return_value="abc123")

        llm = AsyncMock()
        llm.chat = AsyncMock(
            return_value=LLMResponse(
                content=(
                    "family_members:\n"
                    "  - name: Lily\n"
                    "    role: daughter\n"
                    "note: Lily's favorite color is purple\n"
                ),
                model="m",
                usage={},
            )
        )

        result = await process_context_update(
            "Lily is my daughter, she loves purple", llm, "m", store, git
        )

        assert result is True
        ctx = store.read_context()
        assert len(ctx["family"]["members"]) == 1
        assert ctx["notes"][0]["text"] == "Lily's favorite color is purple"

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
