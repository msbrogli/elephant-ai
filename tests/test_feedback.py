"""Tests for brain feedback: sentiment classification + weight math."""

from datetime import date
from unittest.mock import AsyncMock

from elephant.brain.feedback import (
    adjust_weights,
    classify_feedback_sentiment,
    extract_memory_features,
)
from elephant.data.models import Memory, NostalgiaWeights, PreferencesFile
from elephant.llm.client import LLMResponse


def _make_memory(**kwargs):
    defaults = {
        "id": "20260224_test",
        "date": date(2026, 2, 24),
        "title": "Test",
        "type": "daily",
        "description": "Test memory",
        "people": [],
        "source": "WhatsApp",
    }
    defaults.update(kwargs)
    return Memory(**defaults)


class TestClassifySentiment:
    async def test_positive(self):
        llm = AsyncMock()
        llm.chat = AsyncMock(
            return_value=LLMResponse(content="positive", model="m", usage={})
        )
        result = await classify_feedback_sentiment("Love it!", llm, "m")
        assert result == "positive"

    async def test_negative(self):
        llm = AsyncMock()
        llm.chat = AsyncMock(
            return_value=LLMResponse(content="negative", model="m", usage={})
        )
        result = await classify_feedback_sentiment("Too long", llm, "m")
        assert result == "negative"

    async def test_unknown_defaults_to_neutral(self):
        llm = AsyncMock()
        llm.chat = AsyncMock(
            return_value=LLMResponse(content="mixed", model="m", usage={})
        )
        result = await classify_feedback_sentiment("hmm", llm, "m")
        assert result == "neutral"


class TestExtractMemoryFeatures:
    def test_milestone_memories(self):
        memories = [_make_memory(type="milestone", people=["Lily", "Dad"], location="Home")]
        features = extract_memory_features(memories)
        assert features["has_milestone"] is True
        assert features["has_mundane"] is False
        assert features["avg_people"] == 2.0
        assert features["has_location"] is True

    def test_mixed_memories(self):
        memories = [
            _make_memory(type="milestone"),
            _make_memory(type="daily", people=["Lily"]),
        ]
        features = extract_memory_features(memories)
        assert features["has_milestone"] is True
        assert features["has_mundane"] is True
        assert features["avg_people"] == 0.5

    def test_empty_memories(self):
        features = extract_memory_features([])
        assert features["has_milestone"] is False
        assert features["avg_people"] == 0.0


class TestAdjustWeights:
    def test_neutral_no_change(self):
        prefs = PreferencesFile()
        features = {"has_milestone": True}
        result = adjust_weights(prefs, "neutral", features)
        assert result.nostalgia_weights.milestones == 1.0

    def test_positive_boosts_milestone(self):
        prefs = PreferencesFile()
        features = {
            "has_milestone": True, "has_mundane": False,
            "avg_people": 0, "has_location": False,
        }
        result = adjust_weights(prefs, "positive", features)
        assert result.nostalgia_weights.milestones == 1.1

    def test_negative_reduces_milestone(self):
        prefs = PreferencesFile()
        features = {
            "has_milestone": True, "has_mundane": False,
            "avg_people": 0, "has_location": False,
        }
        result = adjust_weights(prefs, "negative", features)
        assert result.nostalgia_weights.milestones == 0.9

    def test_clamp_to_max(self):
        prefs = PreferencesFile(
            nostalgia_weights=NostalgiaWeights(milestones=2.95)
        )
        features = {"has_milestone": True}
        result = adjust_weights(prefs, "positive", features)
        assert result.nostalgia_weights.milestones <= 3.0

    def test_clamp_to_min(self):
        prefs = PreferencesFile(
            nostalgia_weights=NostalgiaWeights(milestones=0.15)
        )
        features = {"has_milestone": True}
        result = adjust_weights(prefs, "negative", features)
        assert result.nostalgia_weights.milestones >= 0.1

    def test_people_boost_adjusts(self):
        prefs = PreferencesFile()
        features = {
            "has_milestone": False, "has_mundane": False,
            "avg_people": 2.5, "has_location": False,
        }
        result = adjust_weights(prefs, "positive", features)
        assert result.nostalgia_weights.people_focus == 1.1

    def test_location_adjusts(self):
        prefs = PreferencesFile()
        features = {
            "has_milestone": False, "has_mundane": False,
            "avg_people": 0, "has_location": True,
        }
        result = adjust_weights(prefs, "positive", features)
        assert result.nostalgia_weights.location_focus == 1.1
