"""Memory milestones & streak tracking: pure functions."""

from __future__ import annotations

from datetime import date, timedelta

MILESTONE_THRESHOLDS = [10, 25, 50, 100, 250, 500, 1000]


def check_memory_milestone(total_count: int, last_celebrated: int) -> int | None:
    """Return the milestone threshold crossed, or None if no new milestone."""
    for threshold in MILESTONE_THRESHOLDS:
        if total_count >= threshold > last_celebrated:
            return threshold
    return None


def compute_streak(last_memory_date: date | None, today: date) -> tuple[int, bool]:
    """Compute the updated streak given the last memory date.

    Returns (new_streak, is_continuation).
    - If last_memory_date is today: streak unchanged, is_continuation=True
    - If last_memory_date is yesterday: streak incremented, is_continuation=True
    - Otherwise: streak resets to 1 (new day with memory), is_continuation=False
    """
    if last_memory_date is None:
        return 1, False

    if last_memory_date == today:
        # Already logged today — no change
        return 0, True

    if last_memory_date == today - timedelta(days=1):
        # Consecutive day
        return 1, True

    # Gap — reset
    return 1, False


def format_milestone_message(threshold: int) -> str:
    """Format a celebration message for a memory milestone."""
    messages = {
        10: "You've logged 10 memories! Your family story is taking shape.",
        25: "25 memories captured! You're building a wonderful archive.",
        50: "50 memories! Half a hundred moments preserved forever.",
        100: "100 memories! What an incredible milestone.",
        250: "250 memories! Your family history is rich and deep.",
        500: "500 memories! You're a true memory keeper.",
        1000: "1,000 memories! A monumental achievement.",
    }
    return f"\U0001f389 {messages.get(threshold, f'{threshold} memories logged!')}"


def format_streak_for_checkin(current_streak: int) -> str | None:
    """Format streak info for the evening check-in. Returns None if streak < 3."""
    if current_streak < 3:
        return None
    return f"You've logged memories {current_streak} days in a row!"
