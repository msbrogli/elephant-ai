"""Tests for prompt templates: each prompt returns valid messages array."""

from elephant.llm.prompts import (
    classify_intent,
    classify_sentiment,
    enrich_context,
    enrich_event,
    evening_checkin,
    generate_clarification,
    generate_question_text,
    morning_digest,
    parse_event,
)

SAMPLE_CONTEXT = {
    "family": {"members": [{"name": "Lily", "role": "daughter"}]},
    "friends": [{"name": "Rafael"}],
    "locations": {"Home": "123 Main St"},
    "notes": ["Dad loves coffee"],
}


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


class TestParseEvent:
    def test_returns_valid_messages(self):
        msgs = parse_event("Lily took her first steps today!", SAMPLE_CONTEXT)
        _assert_valid_messages(msgs)
        assert msgs[0]["role"] == "system"
        assert "YAML" in msgs[0]["content"]

    def test_empty_context(self):
        msgs = parse_event("Something happened", {})
        _assert_valid_messages(msgs)


class TestMorningDigest:
    def test_with_events(self):
        events = [{
            "date": "2025-02-24", "title": "First steps",
            "description": "Walked!", "people": ["Lily"],
            "location": "Home",
        }]
        msgs = morning_digest(events, SAMPLE_CONTEXT)
        _assert_valid_messages(msgs)
        assert "First steps" in msgs[1]["content"]

    def test_no_events(self):
        msgs = morning_digest([], SAMPLE_CONTEXT)
        _assert_valid_messages(msgs)
        assert "No memories" in msgs[1]["content"]

    def test_custom_tone(self):
        msgs = morning_digest([], SAMPLE_CONTEXT, tone_style="playful", tone_length="long")
        _assert_valid_messages(msgs)
        assert "playful" in msgs[0]["content"]


class TestEveningCheckin:
    def test_returns_valid_messages(self):
        msgs = evening_checkin(SAMPLE_CONTEXT)
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
        msgs = generate_clarification("Park day", "Went to park", SAMPLE_CONTEXT)
        _assert_valid_messages(msgs)


class TestEnrichEvent:
    def test_returns_valid_messages(self):
        msgs = enrich_event("Park day", "Went to park", "Who was there?", "Lily and Dad")
        _assert_valid_messages(msgs)


class TestEnrichContext:
    def test_returns_valid_messages(self):
        msgs = enrich_context("My daughter Lily was born on Jan 10 2023", SAMPLE_CONTEXT)
        _assert_valid_messages(msgs)


class TestGenerateQuestionText:
    def test_returns_valid_messages(self):
        msgs = generate_question_text("event_enrichment", "20260224_park", SAMPLE_CONTEXT)
        _assert_valid_messages(msgs)
