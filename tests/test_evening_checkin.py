"""Tests for evening check-in flow: full flow with all deps mocked."""

from unittest.mock import AsyncMock

from elephant.data.store import DataStore
from elephant.flows.evening_checkin import EveningCheckinFlow
from elephant.llm.client import LLMResponse
from elephant.messaging.base import SendResult


class TestEveningCheckinFlow:
    async def test_sends_checkin(self, data_dir):
        store = DataStore(data_dir)
        store.initialize()

        llm = AsyncMock()
        llm.chat = AsyncMock(
            return_value=LLMResponse(
                content="Hey! How was your day? Anything worth remembering?",
                model="test",
                usage={},
            )
        )

        messaging = AsyncMock()
        messaging.broadcast_text = AsyncMock(
            return_value=[SendResult(success=True, message_id="msg_checkin_1")]
        )

        flow = EveningCheckinFlow(store, llm, "test-model", messaging)
        result = await flow.run()

        assert result is True
        messaging.broadcast_text.assert_called_once()
        call_text = messaging.broadcast_text.call_args[0][0]
        assert len(call_text) > 0

    async def test_handles_send_failure(self, data_dir):
        store = DataStore(data_dir)
        store.initialize()

        llm = AsyncMock()
        llm.chat = AsyncMock(
            return_value=LLMResponse(content="Check-in text", model="test", usage={})
        )

        messaging = AsyncMock()
        messaging.broadcast_text = AsyncMock(
            return_value=[SendResult(success=False, error="Network error")]
        )

        flow = EveningCheckinFlow(store, llm, "test-model", messaging)
        result = await flow.run()

        assert result is False
