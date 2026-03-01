"""Tests for memory parser: mocked LLM -> Memory."""

from datetime import date
from unittest.mock import AsyncMock

import pytest

from elephant.data.models import Memory, Person, PreferencesFile
from elephant.llm.client import LLMResponse
from elephant.memory_parser import (
    ParseResult,
    parse_memories_from_document,
    parse_memory_from_text,
)


class TestParseMemoryFromText:
    async def test_parses_valid_response(self):
        llm = AsyncMock()
        llm.chat = AsyncMock(
            return_value=LLMResponse(
                content=(
                    "title: Lily's first steps\n"
                    "type: milestone\n"
                    "description: Lily took 4 steps toward Dad!\n"
                    "people:\n  - Lily\n  - Dad\n"
                    "location: Portland, OR\n"
                    "nostalgia_score: 1.5\n"
                    "tags:\n  - baby\n  - milestone"
                ),
                model="test",
                usage={},
            )
        )

        people: list[Person] = []
        prefs = PreferencesFile()
        result = await parse_memory_from_text(
            "Lily took her first steps today!",
            llm,
            "test-model",
            people,
            prefs,
            memory_date=date(2026, 2, 24),
        )

        assert isinstance(result, ParseResult)
        memory = result.memory
        assert isinstance(memory, Memory)
        assert memory.title == "Lily's first steps"
        assert memory.type == "milestone"
        assert memory.people == ["Lily", "Dad"]
        assert memory.location == "Portland, OR"
        assert memory.nostalgia_score == 1.5
        assert "baby" in memory.tags
        assert memory.date == date(2026, 2, 24)
        assert memory.id.startswith("20260224_")
        assert result.confidence == 1.0  # default when not specified

    async def test_uses_defaults_for_missing_fields(self):
        llm = AsyncMock()
        llm.chat = AsyncMock(
            return_value=LLMResponse(
                content=(
                    "title: Quick note\ntype: mundane\n"
                    "description: Something happened\n"
                    "people: []\nnostalgia_score: 0.5\ntags: []"
                ),
                model="test",
                usage={},
            )
        )

        people: list[Person] = []
        prefs = PreferencesFile()
        result = await parse_memory_from_text(
            "Something happened",
            llm,
            "test-model",
            people,
            prefs,
            memory_date=date(2026, 2, 24),
        )

        assert result.memory.title == "Quick note"
        assert result.memory.location is None
        assert result.memory.source == "WhatsApp"

    async def test_invalid_llm_response_raises(self):
        llm = AsyncMock()
        llm.chat = AsyncMock(
            return_value=LLMResponse(content="just a string", model="test", usage={})
        )

        people: list[Person] = []
        prefs = PreferencesFile()
        with pytest.raises(ValueError, match="non-dict"):
            await parse_memory_from_text(
                "test",
                llm,
                "test-model",
                people,
                prefs,
                memory_date=date(2026, 2, 24),
            )

    async def test_integer_time_coerced_to_string(self):
        llm = AsyncMock()
        llm.chat = AsyncMock(
            return_value=LLMResponse(
                content=(
                    "title: Morning walk\ntype: daily\ntime: 1020\n"
                    "description: Walked in the park\npeople: []\ntags: []"
                ),
                model="test",
                usage={},
            )
        )

        people: list[Person] = []
        prefs = PreferencesFile()
        result = await parse_memory_from_text(
            "Morning walk at 10:20",
            llm,
            "test-model",
            people,
            prefs,
            memory_date=date(2026, 2, 25),
        )

        assert result.memory.time == "1020"

    async def test_custom_source(self):
        llm = AsyncMock()
        llm.chat = AsyncMock(
            return_value=LLMResponse(
                content="title: Park\ntype: daily\ndescription: Park day\npeople: []\ntags: []",
                model="test",
                usage={},
            )
        )

        people: list[Person] = []
        prefs = PreferencesFile()
        result = await parse_memory_from_text(
            "Went to park",
            llm,
            "test-model",
            people,
            prefs,
            source="Telegram",
            memory_date=date(2026, 2, 24),
        )

        assert result.memory.source == "Telegram"


class TestParseMemoriesFromDocument:
    async def test_parses_yaml_list(self):
        llm = AsyncMock()
        llm.chat = AsyncMock(
            return_value=LLMResponse(
                content=(
                    "- title: Mom's birthday\n"
                    "  type: celebration\n"
                    "  date: 2026-03-15\n"
                    "  description: Mom's birthday\n"
                    "  people: [Mom]\n"
                    "  location: null\n"
                    "  nostalgia_score: 1.5\n"
                    "  tags: [birthday]\n"
                    "- title: Dad's birthday\n"
                    "  type: celebration\n"
                    "  date: 2026-07-20\n"
                    "  description: Dad's birthday\n"
                    "  people: [Dad]\n"
                    "  location: null\n"
                    "  nostalgia_score: 1.5\n"
                    "  tags: [birthday]"
                ),
                model="test",
                usage={},
            )
        )

        people: list[Person] = []
        prefs = PreferencesFile()
        memories = await parse_memories_from_document(
            caption="These are birthdays",
            document_content='[{"name":"Mom","due":"2026-03-15"},{"name":"Dad","due":"2026-07-20"}]',
            llm=llm,
            model="test-model",
            people=people,
            prefs=prefs,
        )

        assert len(memories) == 2
        assert all(isinstance(m, Memory) for m in memories)
        assert memories[0].title == "Mom's birthday"
        assert memories[0].date == date(2026, 3, 15)
        assert memories[1].title == "Dad's birthday"
        assert memories[1].date == date(2026, 7, 20)

    async def test_single_dict_wrapped_as_list(self):
        llm = AsyncMock()
        llm.chat = AsyncMock(
            return_value=LLMResponse(
                content=(
                    "title: Solo memory\n"
                    "type: daily\n"
                    "date: 2026-01-01\n"
                    "description: A single memory\n"
                    "people: []\n"
                    "location: null\n"
                    "nostalgia_score: 1.0\n"
                    "tags: []"
                ),
                model="test",
                usage={},
            )
        )

        people: list[Person] = []
        prefs = PreferencesFile()
        memories = await parse_memories_from_document(
            caption="One memory",
            document_content="some content",
            llm=llm,
            model="test-model",
            people=people,
            prefs=prefs,
        )

        assert len(memories) == 1
        assert memories[0].title == "Solo memory"

    async def test_empty_list_returns_empty(self):
        llm = AsyncMock()
        llm.chat = AsyncMock(
            return_value=LLMResponse(content="[]", model="test", usage={})
        )

        people: list[Person] = []
        prefs = PreferencesFile()
        memories = await parse_memories_from_document(
            caption="Empty file",
            document_content="",
            llm=llm,
            model="test-model",
            people=people,
            prefs=prefs,
        )

        assert memories == []

    async def test_integer_time_coerced_to_string(self):
        llm = AsyncMock()
        llm.chat = AsyncMock(
            return_value=LLMResponse(
                content=(
                    "- title: Lunch\n"
                    "  type: daily\n"
                    "  date: 2026-02-25\n"
                    "  time: 1230\n"
                    "  description: Had lunch\n"
                    "  people: []\n"
                    "  nostalgia_score: 0.5\n"
                    "  tags: []"
                ),
                model="test",
                usage={},
            )
        )

        people: list[Person] = []
        prefs = PreferencesFile()
        memories = await parse_memories_from_document(
            caption="Memories",
            document_content="some data",
            llm=llm,
            model="test-model",
            people=people,
            prefs=prefs,
        )

        assert len(memories) == 1
        assert memories[0].time == "1230"

    async def test_invalid_response_raises(self):
        llm = AsyncMock()
        llm.chat = AsyncMock(
            return_value=LLMResponse(content="just a string", model="test", usage={})
        )

        people: list[Person] = []
        prefs = PreferencesFile()
        with pytest.raises(ValueError, match="unexpected type"):
            await parse_memories_from_document(
                caption="test",
                document_content="test",
                llm=llm,
                model="test-model",
                people=people,
                prefs=prefs,
            )
