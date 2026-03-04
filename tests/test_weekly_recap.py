"""Tests for weekly recap flow."""

from __future__ import annotations

from datetime import date, timedelta
from unittest.mock import AsyncMock, patch

from elephant.data.models import Memory
from elephant.data.store import DataStore
from elephant.flows.weekly_recap import WeeklyRecapFlow
from elephant.llm.client import LLMResponse
from elephant.messaging.base import SendResult


class TestWeeklyRecapFlow:
    async def test_sends_recap_with_memories(self, data_dir):
        store = DataStore(data_dir)
        store.initialize()

        today = date(2026, 3, 1)
        for i in range(3):
            store.write_memory(
                Memory(
                    id=f"20260225_event_{i}",
                    date=today - timedelta(days=i + 1),
                    title=f"Event {i}",
                    type="daily",
                    description=f"Something happened {i}",
                    people=["Lily", "Dad"] if i < 2 else ["Mom"],
                    source="Telegram",
                    nostalgia_score=1.0 + i * 0.5,
                )
            )

        llm = AsyncMock()
        llm.chat = AsyncMock(
            return_value=LLMResponse(
                content="What a lovely week! Here's your recap...",
                model="test",
                usage={},
            )
        )

        messaging = AsyncMock()
        messaging.broadcast_text = AsyncMock(
            return_value=[SendResult(success=True, message_id="msg_recap_1")]
        )

        flow = WeeklyRecapFlow(store, llm, "test-model", messaging)
        with patch("elephant.flows.weekly_recap.date") as mock_date:
            mock_date.today.return_value = today
            mock_date.side_effect = lambda *a, **kw: date(*a, **kw)
            result = await flow.run()

        assert result is True
        messaging.broadcast_text.assert_called_once()
        llm.chat.assert_called_once()

        # Check LLM prompt includes memory count
        call_args = llm.chat.call_args[0][0]
        user_msg = call_args[1]["content"]
        assert "3 memories logged" in user_msg
        assert "people mentioned" in user_msg

    async def test_sends_with_zero_memories(self, data_dir):
        """Recap sends encouraging message when no memories exist."""
        store = DataStore(data_dir)
        store.initialize()

        llm = AsyncMock()
        llm.chat = AsyncMock(
            return_value=LLMResponse(
                content="No memories this week, but every day is a new chance!",
                model="test",
                usage={},
            )
        )

        messaging = AsyncMock()
        messaging.broadcast_text = AsyncMock(
            return_value=[SendResult(success=True, message_id="msg_recap_2")]
        )

        flow = WeeklyRecapFlow(store, llm, "test-model", messaging)
        with patch("elephant.flows.weekly_recap.date") as mock_date:
            mock_date.today.return_value = date(2026, 3, 1)
            mock_date.side_effect = lambda *a, **kw: date(*a, **kw)
            result = await flow.run()

        assert result is True
        messaging.broadcast_text.assert_called_once()

        # Check LLM prompt says 0 memories
        call_args = llm.chat.call_args[0][0]
        user_msg = call_args[1]["content"]
        assert "0 memories logged" in user_msg

    async def test_send_failure_returns_false(self, data_dir):
        store = DataStore(data_dir)
        store.initialize()

        llm = AsyncMock()
        llm.chat = AsyncMock(
            return_value=LLMResponse(content="Recap text", model="test", usage={})
        )

        messaging = AsyncMock()
        messaging.broadcast_text = AsyncMock(
            return_value=[SendResult(success=False, error="Network error")]
        )

        flow = WeeklyRecapFlow(store, llm, "test-model", messaging)
        result = await flow.run()

        assert result is False

    async def test_metric_incremented_on_success(self, data_dir):
        store = DataStore(data_dir)
        store.initialize()

        llm = AsyncMock()
        llm.chat = AsyncMock(
            return_value=LLMResponse(content="Recap", model="test", usage={})
        )

        messaging = AsyncMock()
        messaging.broadcast_text = AsyncMock(
            return_value=[SendResult(success=True, message_id="msg_recap_3")]
        )

        flow = WeeklyRecapFlow(store, llm, "test-model", messaging)
        await flow.run()

        metrics = store.read_metrics()
        today_metrics = [d for d in metrics.days if d.date == date.today()]
        assert len(today_metrics) == 1
        assert today_metrics[0].weekly_recaps_sent == 1
