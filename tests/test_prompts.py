"""Tests for prompt templates: each prompt returns valid messages array."""

from elephant.data.models import Person, PreferencesFile
from elephant.llm.prompts import (
    classify_intent,
    classify_sentiment,
    enrich_memory,
    evening_checkin,
    generate_clarification,
    generate_question_text,
    morning_digest,
    parse_memory,
)

SAMPLE_PEOPLE = [
    Person(person_id="lily", display_name="Lily", relationship=["daughter"]),
    Person(person_id="rafael", display_name="Rafael", relationship=["friend"]),
]

SAMPLE_PREFS = PreferencesFile(
    locations={"Home": "123 Main St"},
    notes=["Dad loves coffee"],
)


def _assert_valid_messages(messages):
    """Assert messages is a list of dicts with role and content."""
    assert isinstance(messages, list)
    assert len(messages) >= 2
    for msg in messages:
        assert "role" in msg
        assert "content" in msg
        assert msg["role"] in ("system", "user", "assistant")
        assert isinstance(msg["content"], str)
        assert len(msg["content"]) > 0


class TestParseMemory:
    def test_returns_valid_messages(self):
        msgs = parse_memory("Lily took her first steps today!", SAMPLE_PEOPLE, SAMPLE_PREFS)
        _assert_valid_messages(msgs)
        assert msgs[0]["role"] == "system"
        assert "YAML" in msgs[0]["content"]

    def test_empty_context(self):
        msgs = parse_memory("Something happened", [], PreferencesFile())
        _assert_valid_messages(msgs)


class TestMorningDigest:
    def test_with_memories(self):
        memories = [{
            "date": "2025-02-24", "title": "First steps",
            "description": "Walked!", "people": ["Lily"],
            "location": "Home",
        }]
        msgs = morning_digest(memories, SAMPLE_PEOPLE, SAMPLE_PREFS)
        _assert_valid_messages(msgs)
        assert "First steps" in msgs[1]["content"]

    def test_no_memories(self):
        msgs = morning_digest([], SAMPLE_PEOPLE, SAMPLE_PREFS)
        _assert_valid_messages(msgs)
        assert "No memories" in msgs[1]["content"]

    def test_custom_tone(self):
        msgs = morning_digest(
            [], SAMPLE_PEOPLE, SAMPLE_PREFS, tone_style="playful", tone_length="long",
        )
        _assert_valid_messages(msgs)
        assert "playful" in msgs[0]["content"]


class TestEveningCheckin:
    def test_returns_valid_messages(self):
        msgs = evening_checkin(SAMPLE_PEOPLE, SAMPLE_PREFS)
        _assert_valid_messages(msgs)


class TestClassifyIntent:
    def test_with_recent_digest(self):
        msgs = classify_intent("love it!", has_recent_digest=True)
        _assert_valid_messages(msgs)
        assert "recently sent" in msgs[0]["content"]

    def test_without_recent_digest(self):
        msgs = classify_intent("my daughter is Lily", has_recent_digest=False)
        _assert_valid_messages(msgs)


class TestClassifySentiment:
    def test_returns_valid_messages(self):
        msgs = classify_sentiment("I loved today's digest!")
        _assert_valid_messages(msgs)
        assert msgs[0]["role"] == "system"


class TestGenerateClarification:
    def test_returns_valid_messages(self):
        msgs = generate_clarification("Park day", "Went to park", SAMPLE_PEOPLE, SAMPLE_PREFS)
        _assert_valid_messages(msgs)


class TestEnrichMemory:
    def test_returns_valid_messages(self):
        msgs = enrich_memory("Park day", "Went to park", "Who was there?", "Lily and Dad")
        _assert_valid_messages(msgs)


class TestGenerateQuestionText:
    def test_returns_valid_messages(self):
        msgs = generate_question_text(
            "memory_enrichment", "20260224_park", SAMPLE_PEOPLE, SAMPLE_PREFS,
        )
        _assert_valid_messages(msgs)
