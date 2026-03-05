"""Tests for memory milestones & streak tracking."""

from __future__ import annotations

from datetime import date

from elephant.brain.milestones import (
    check_memory_milestone,
    compute_streak,
    format_milestone_message,
    format_streak_for_checkin,
)


class TestCheckMemoryMilestone:
    def test_no_milestone_below_first_threshold(self) -> None:
        assert check_memory_milestone(5, 0) is None

    def test_crosses_first_threshold(self) -> None:
        assert check_memory_milestone(10, 0) == 10

    def test_crosses_middle_threshold(self) -> None:
        assert check_memory_milestone(50, 25) == 50

    def test_already_celebrated(self) -> None:
        assert check_memory_milestone(10, 10) is None

    def test_crosses_highest(self) -> None:
        assert check_memory_milestone(1000, 500) == 1000

    def test_exact_threshold(self) -> None:
        assert check_memory_milestone(25, 10) == 25

    def test_between_thresholds(self) -> None:
        assert check_memory_milestone(30, 25) is None

    def test_skips_to_correct_threshold(self) -> None:
        # If someone jumps from 5 to 60, they should get 10 (the first uncelebrated)
        assert check_memory_milestone(60, 0) == 10


class TestComputeStreak:
    def test_first_ever_memory(self) -> None:
        streak, is_continuation = compute_streak(None, date(2026, 3, 1))
        assert streak == 1
        assert is_continuation is False

    def test_consecutive_day(self) -> None:
        yesterday = date(2026, 2, 28)
        today = date(2026, 3, 1)
        streak, is_continuation = compute_streak(yesterday, today)
        assert streak == 1
        assert is_continuation is True

    def test_same_day(self) -> None:
        today = date(2026, 3, 1)
        streak, is_continuation = compute_streak(today, today)
        assert streak == 0
        assert is_continuation is True

    def test_gap_resets(self) -> None:
        two_days_ago = date(2026, 2, 27)
        today = date(2026, 3, 1)
        streak, is_continuation = compute_streak(two_days_ago, today)
        assert streak == 1
        assert is_continuation is False


class TestFormatMilestoneMessage:
    def test_known_threshold(self) -> None:
        msg = format_milestone_message(100)
        assert "100 memories" in msg
        assert "\U0001f389" in msg

    def test_unknown_threshold(self) -> None:
        msg = format_milestone_message(999)
        assert "999 memories" in msg


class TestFormatStreakForCheckin:
    def test_short_streak_returns_none(self) -> None:
        assert format_streak_for_checkin(2) is None
        assert format_streak_for_checkin(0) is None

    def test_three_day_streak(self) -> None:
        result = format_streak_for_checkin(3)
        assert result is not None
        assert "3 days" in result

    def test_long_streak(self) -> None:
        result = format_streak_for_checkin(10)
        assert result is not None
        assert "10 days" in result
