"""Tests for monthly report flow."""

from __future__ import annotations

from datetime import date
from unittest.mock import AsyncMock, patch

from elephant.data.models import (
    DailyMetrics,
    Memory,
    MetricsFile,
    NostalgiaWeights,
    PreferencesFile,
    TonePreference,
)
from elephant.data.store import DataStore
from elephant.flows.monthly_report import MonthlyReportFlow
from elephant.messaging.base import SendResult


class TestMonthlyReportFlow:
    async def test_sends_report_with_data(self, data_dir):
        store = DataStore(data_dir)
        store.initialize()

        # Create memories in February 2026
        for i in range(3):
            store.write_memory(
                Memory(
                    id=f"20260215_event_{i}",
                    date=date(2026, 2, 15),
                    title=f"Event {i}",
                    type="daily",
                    description=f"Something {i}",
                    people=["Lily", "Dad"] if i < 2 else ["Mom"],
                    source="Telegram",
                )
            )

        # Write metrics for February
        store.write_metrics(
            MetricsFile(
                days=[
                    DailyMetrics(
                        date=date(2026, 2, 15),
                        digests_sent=1,
                        digest_replies=1,
                        checkins_sent=1,
                    ),
                    DailyMetrics(
                        date=date(2026, 2, 20),
                        digests_sent=1,
                        checkins_sent=1,
                    ),
                ]
            )
        )

        # Write preferences with adjusted weights
        prefs = PreferencesFile(
            nostalgia_weights=NostalgiaWeights(milestones=1.8, people_focus=1.5),
            tone_preference=TonePreference(style="heartfelt", length="short"),
        )
        store.write_preferences(prefs)

        messaging = AsyncMock()
        messaging.broadcast_text = AsyncMock(
            return_value=[SendResult(success=True, message_id="msg_report_1")]
        )

        flow = MonthlyReportFlow(store=store, messaging=messaging)

        # Run on March 1st 2026
        with patch("elephant.flows.monthly_report.date") as mock_date:
            mock_date.today.return_value = date(2026, 3, 1)
            mock_date.side_effect = lambda *a, **kw: date(*a, **kw)
            result = await flow.run()

        assert result is True
        messaging.broadcast_text.assert_called_once()

        report_text = messaging.broadcast_text.call_args[0][0]
        assert "February 2026" in report_text
        assert "3 captured" in report_text
        assert "Lily" in report_text
        assert "high priority (1.8)" in report_text
        assert "2 digests sent" in report_text

    async def test_empty_month(self, data_dir):
        """Report still sends even when no memories exist."""
        store = DataStore(data_dir)
        store.initialize()

        messaging = AsyncMock()
        messaging.broadcast_text = AsyncMock(
            return_value=[SendResult(success=True, message_id="msg_report_2")]
        )

        flow = MonthlyReportFlow(store=store, messaging=messaging)

        with patch("elephant.flows.monthly_report.date") as mock_date:
            mock_date.today.return_value = date(2026, 3, 1)
            mock_date.side_effect = lambda *a, **kw: date(*a, **kw)
            result = await flow.run()

        assert result is True
        report_text = messaging.broadcast_text.call_args[0][0]
        assert "0 captured" in report_text

    async def test_send_failure(self, data_dir):
        store = DataStore(data_dir)
        store.initialize()

        messaging = AsyncMock()
        messaging.broadcast_text = AsyncMock(
            return_value=[SendResult(success=False, error="Network error")]
        )

        flow = MonthlyReportFlow(store=store, messaging=messaging)

        with patch("elephant.flows.monthly_report.date") as mock_date:
            mock_date.today.return_value = date(2026, 3, 1)
            mock_date.side_effect = lambda *a, **kw: date(*a, **kw)
            result = await flow.run()

        assert result is False

    async def test_january_report_covers_december(self, data_dir):
        """Running in January should report on December of the previous year."""
        store = DataStore(data_dir)
        store.initialize()

        messaging = AsyncMock()
        messaging.broadcast_text = AsyncMock(
            return_value=[SendResult(success=True, message_id="msg_report_3")]
        )

        flow = MonthlyReportFlow(store=store, messaging=messaging)

        with patch("elephant.flows.monthly_report.date") as mock_date:
            mock_date.today.return_value = date(2027, 1, 1)
            mock_date.side_effect = lambda *a, **kw: date(*a, **kw)
            result = await flow.run()

        assert result is True
        report_text = messaging.broadcast_text.call_args[0][0]
        assert "December 2026" in report_text
