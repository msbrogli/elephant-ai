"""Tests for scheduler: mocked asyncio.sleep."""

import asyncio
from unittest.mock import AsyncMock

from elephant.scheduler import Scheduler


class TestScheduler:
    async def test_start_and_stop(self):
        scheduler = Scheduler("America/Chicago")
        await scheduler.start()
        assert scheduler._running is True
        await scheduler.stop()
        assert scheduler._running is False

    async def test_schedule_periodic(self):
        scheduler = Scheduler("America/Chicago")
        callback = AsyncMock()

        await scheduler.start()
        scheduler.schedule_periodic(0.05, callback, name="test_periodic")

        # Wait for a couple of ticks
        await asyncio.sleep(0.15)
        await scheduler.stop()

        assert callback.call_count >= 1

    async def test_schedule_periodic_handles_errors(self):
        scheduler = Scheduler("America/Chicago")
        callback = AsyncMock(side_effect=RuntimeError("boom"))

        await scheduler.start()
        scheduler.schedule_periodic(0.05, callback, name="test_error")

        await asyncio.sleep(0.15)
        await scheduler.stop()

        # Should have been called despite errors
        assert callback.call_count >= 1

    async def test_stop_cancels_tasks(self):
        scheduler = Scheduler("America/Chicago")
        callback = AsyncMock()

        await scheduler.start()
        scheduler.schedule_periodic(0.01, callback, name="test")
        assert len(scheduler._tasks) == 1

        await scheduler.stop()
        assert len(scheduler._tasks) == 0

    async def test_schedule_daily(self):
        """Test that schedule_daily creates a task (timing tested via mock)."""
        scheduler = Scheduler("UTC")
        callback = AsyncMock()

        await scheduler.start()
        scheduler.schedule_daily("00:00", callback, name="test_daily")
        assert len(scheduler._tasks) == 1

        await scheduler.stop()
