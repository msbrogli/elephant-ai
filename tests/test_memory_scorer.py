"""Tests for memory scorer: deterministic scoring."""

from datetime import date

from elephant.data.models import Memory, NostalgiaWeights
from elephant.memory_scorer import score_memory


def _make_memory(**kwargs):
    defaults = {
        "id": "20260224_test",
        "date": date(2026, 2, 24),
        "title": "Test memory",
        "type": "daily",
        "description": "Test",
        "people": [],
        "source": "WhatsApp",
        "nostalgia_score": 1.0,
    }
    defaults.update(kwargs)
    return Memory(**defaults)


class TestScoreMemory:
    def test_basic_daily_memory(self):
        memory = _make_memory()
        weights = NostalgiaWeights()
        score = score_memory(memory, weights)
        # base (1.0 * 1.0) + people (1.0 * 0/3) + location (0) = 1.0
        assert score == 1.0

    def test_milestone_gets_milestone_weight(self):
        memory = _make_memory(type="milestone", nostalgia_score=1.5)
        weights = NostalgiaWeights(milestones=2.0)
        score = score_memory(memory, weights)
        # base (1.5 * 2.0) + people (1.0 * 0/3) + location (0) = 3.0
        assert score == 3.0

    def test_celebration_gets_milestone_weight(self):
        memory = _make_memory(type="celebration")
        weights = NostalgiaWeights(milestones=1.5)
        score = score_memory(memory, weights)
        # base (1.0 * 1.5) + people (1.0 * 0/3) + location (0) = 1.5
        assert score == 1.5

    def test_people_boost(self):
        memory = _make_memory(people=["Lily", "Dad", "Mom"])
        weights = NostalgiaWeights(people_focus=1.5)
        score = score_memory(memory, weights)
        # base (1.0 * 1.0) + people (1.5 * 3/3) + location (0) = 2.5
        assert score == 2.5

    def test_location_boost(self):
        memory = _make_memory(location="Portland, OR")
        weights = NostalgiaWeights(location_focus=0.5)
        score = score_memory(memory, weights)
        # base (1.0 * 1.0) + people (1.0 * 0/3) + location (0.5) = 1.5
        assert score == 1.5

    def test_all_factors(self):
        memory = _make_memory(
            type="milestone",
            nostalgia_score=2.0,
            people=["Lily", "Dad", "Mom"],
            location="Portland, OR",
        )
        weights = NostalgiaWeights(
            milestones=1.5,
            people_focus=2.0,
            location_focus=1.0,
        )
        score = score_memory(memory, weights)
        # base (2.0 * 1.5) + people (2.0 * 3/3) + location (1.0)
        # = 3.0 + 2.0 + 1.0 = 6.0
        assert score == 6.0

    def test_mundane_type_uses_mundane_weight(self):
        memory = _make_memory(type="mundane")
        weights = NostalgiaWeights(mundane_daily=0.5)
        score = score_memory(memory, weights)
        # base (1.0 * 0.5) + 0 + 0 = 0.5
        assert score == 0.5
