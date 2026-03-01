"""Tests for context resolver: all intent branches."""

from datetime import UTC, datetime, timedelta

from elephant.context_resolver import Intent, resolve_intent
from elephant.data.models import DigestState, PendingQuestion, PendingQuestionsFile
from elephant.messaging.base import IncomingMessage


def _make_message(
    text="test",
    reply_to_id=None,
    timestamp=None,
):
    return IncomingMessage(
        text=text,
        sender="user123",
        message_id="msg_1",
        timestamp=timestamp or datetime.now(UTC),
        reply_to_id=reply_to_id,
    )


class TestResolveIntent:
    async def test_reply_to_digest_message(self):
        msg = _make_message(text="love it!", reply_to_id="digest_msg_1")
        digest = DigestState(
            last_digest_sent_at=datetime.now(UTC),
            last_digest_message_id="digest_msg_1",
        )
        pq = PendingQuestionsFile()

        intent = await resolve_intent(msg, digest, pq)
        assert intent == Intent.DIGEST_FEEDBACK

    async def test_reply_to_question(self):
        msg = _make_message(text="Lily and Dad", reply_to_id="42")
        digest = DigestState()
        pq = PendingQuestionsFile(
            questions=[
                PendingQuestion(
                    id="q_001",
                    type="memory_enrichment",
                    subject="20260224_park",
                    status="asked",
                    created_at=datetime.now(UTC),
                    message_id="42",
                )
            ]
        )

        intent = await resolve_intent(msg, digest, pq)
        assert intent == Intent.ANSWER_TO_QUESTION

    async def test_reply_to_question_without_message_id_falls_through(self):
        """Questions without message_id should not match replies."""
        msg = _make_message(text="Lily and Dad", reply_to_id="42")
        digest = DigestState()
        pq = PendingQuestionsFile(
            questions=[
                PendingQuestion(
                    id="q_001",
                    type="memory_enrichment",
                    subject="20260224_park",
                    status="asked",
                    created_at=datetime.now(UTC),
                    message_id=None,
                )
            ]
        )

        intent = await resolve_intent(msg, digest, pq, llm=None)
        assert intent == Intent.NEW_MEMORY

    async def test_within_digest_window(self):
        now = datetime.now(UTC)
        msg = _make_message(text="nice!", timestamp=now)
        digest = DigestState(
            last_digest_sent_at=now - timedelta(minutes=10),
        )
        pq = PendingQuestionsFile()

        intent = await resolve_intent(msg, digest, pq)
        assert intent == Intent.DIGEST_FEEDBACK

    async def test_outside_digest_window_defaults_to_new_memory(self):
        now = datetime.now(UTC)
        msg = _make_message(text="Lily walked today!", timestamp=now)
        digest = DigestState(
            last_digest_sent_at=now - timedelta(hours=2),
        )
        pq = PendingQuestionsFile()

        # Without LLM, default is NEW_MEMORY
        intent = await resolve_intent(msg, digest, pq, llm=None)
        assert intent == Intent.NEW_MEMORY

    async def test_no_digest_state_defaults_to_new_memory(self):
        msg = _make_message(text="We went to the park")
        digest = DigestState()
        pq = PendingQuestionsFile()

        intent = await resolve_intent(msg, digest, pq, llm=None)
        assert intent == Intent.NEW_MEMORY

    async def test_llm_classifies_context_update(self):
        from unittest.mock import AsyncMock

        from elephant.llm.client import LLMResponse

        mock_llm = AsyncMock()
        mock_llm.chat = AsyncMock(
            return_value=LLMResponse(content="context_update", model="m", usage={})
        )

        now = datetime.now(UTC)
        msg = _make_message(text="My daughter Lily was born on Jan 10", timestamp=now)
        digest = DigestState(
            last_digest_sent_at=now - timedelta(hours=5),
        )
        pq = PendingQuestionsFile()

        intent = await resolve_intent(msg, digest, pq, llm=mock_llm)
        assert intent == Intent.CONTEXT_UPDATE
