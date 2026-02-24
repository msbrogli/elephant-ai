"""Tests for event parser: mocked LLM -> Event."""

from datetime import date
from unittest.mock import AsyncMock

import pytest

from elephant.data.models import Event
from elephant.event_parser import parse_event_from_text, parse_events_from_document
from elephant.llm.client import LLMResponse


class TestParseEventFromText:
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

        event = await parse_event_from_text(
            "Lily took her first steps today!",
            llm,
            "test-model",
            {},
            event_date=date(2026, 2, 24),
        )

        assert isinstance(event, Event)
        assert event.title == "Lily's first steps"
        assert event.type == "milestone"
        assert event.people == ["Lily", "Dad"]
        assert event.location == "Portland, OR"
        assert event.nostalgia_score == 1.5
        assert "baby" in event.tags
        assert event.date == date(2026, 2, 24)
        assert event.id.startswith("20260224_")

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

        event = await parse_event_from_text(
            "Something happened",
            llm,
            "test-model",
            {},
            event_date=date(2026, 2, 24),
        )

        assert event.title == "Quick note"
        assert event.location is None
        assert event.source == "WhatsApp"

    async def test_invalid_llm_response_raises(self):
        llm = AsyncMock()
        llm.chat = AsyncMock(
            return_value=LLMResponse(content="just a string", model="test", usage={})
        )

        with pytest.raises(ValueError, match="non-dict"):
            await parse_event_from_text(
                "test",
                llm,
                "test-model",
                {},
                event_date=date(2026, 2, 24),
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

        event = await parse_event_from_text(
            "Morning walk at 10:20",
            llm,
            "test-model",
            {},
            event_date=date(2026, 2, 25),
        )

        assert event.time == "1020"

    async def test_custom_source(self):
        llm = AsyncMock()
        llm.chat = AsyncMock(
            return_value=LLMResponse(
                content="title: Park\ntype: daily\ndescription: Park day\npeople: []\ntags: []",
                model="test",
                usage={},
            )
        )

        event = await parse_event_from_text(
            "Went to park",
            llm,
            "test-model",
            {},
            source="Telegram",
            event_date=date(2026, 2, 24),
        )

        assert event.source == "Telegram"


class TestParseEventsFromDocument:
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

        events = await parse_events_from_document(
            caption="These are birthdays",
            document_content='[{"name":"Mom","due":"2026-03-15"},{"name":"Dad","due":"2026-07-20"}]',
            llm=llm,
            model="test-model",
            context={},
        )

        assert len(events) == 2
        assert all(isinstance(e, Event) for e in events)
        assert events[0].title == "Mom's birthday"
        assert events[0].date == date(2026, 3, 15)
        assert events[1].title == "Dad's birthday"
        assert events[1].date == date(2026, 7, 20)

    async def test_single_dict_wrapped_as_list(self):
        llm = AsyncMock()
        llm.chat = AsyncMock(
            return_value=LLMResponse(
                content=(
                    "title: Solo event\n"
                    "type: daily\n"
                    "date: 2026-01-01\n"
                    "description: A single event\n"
                    "people: []\n"
                    "location: null\n"
                    "nostalgia_score: 1.0\n"
                    "tags: []"
                ),
                model="test",
                usage={},
            )
        )

        events = await parse_events_from_document(
            caption="One event",
            document_content="some content",
            llm=llm,
            model="test-model",
            context={},
        )

        assert len(events) == 1
        assert events[0].title == "Solo event"

    async def test_empty_list_returns_empty(self):
        llm = AsyncMock()
        llm.chat = AsyncMock(
            return_value=LLMResponse(content="[]", model="test", usage={})
        )

        events = await parse_events_from_document(
            caption="Empty file",
            document_content="",
            llm=llm,
            model="test-model",
            context={},
        )

        assert events == []

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

        events = await parse_events_from_document(
            caption="Events",
            document_content="some data",
            llm=llm,
            model="test-model",
            context={},
        )

        assert len(events) == 1
        assert events[0].time == "1230"

    async def test_invalid_response_raises(self):
        llm = AsyncMock()
        llm.chat = AsyncMock(
            return_value=LLMResponse(content="just a string", model="test", usage={})
        )

        with pytest.raises(ValueError, match="unexpected type"):
            await parse_events_from_document(
                caption="test",
                document_content="test",
                llm=llm,
                model="test-model",
                context={},
            )
