"""Tests for brain question manager: pending question sending."""

from datetime import UTC, datetime
from unittest.mock import AsyncMock

from elephant.brain.question_manager import QuestionManager
from elephant.data.models import PendingQuestion, PendingQuestionsFile
from elephant.data.store import DataStore
from elephant.llm.client import LLMResponse
from elephant.messaging.base import SendResult


class TestQuestionManager:
    async def test_sends_pending_question(self, data_dir):
        store = DataStore(data_dir)
        store.initialize()

        pq = PendingQuestionsFile(
            questions=[
                PendingQuestion(
                    id="q_001",
                    type="memory_enrichment",
                    subject="20260224_park",
                    question="Who was at the park?",
                    status="pending",
                    created_at=datetime.now(UTC),
                )
            ]
        )
        store.write_pending_questions(pq)

        llm = AsyncMock()
        messaging = AsyncMock()
        messaging.broadcast_text = AsyncMock(
            return_value=[SendResult(success=True, message_id="msg_1")]
        )

        mgr = QuestionManager(store, llm, "m", messaging)
        count = await mgr.process_pending()

        assert count == 1
        messaging.broadcast_text.assert_called_once_with("Who was at the park?")

        # Verify status and message_id updated
        updated = store.read_pending_questions()
        assert updated.questions[0].status == "asked"
        assert updated.questions[0].message_id == "msg_1"

    async def test_generates_question_text_if_missing(self, data_dir):
        store = DataStore(data_dir)
        store.initialize()

        pq = PendingQuestionsFile(
            questions=[
                PendingQuestion(
                    id="q_002",
                    type="memory_enrichment",
                    subject="20260224_park",
                    question=None,  # No text yet
                    status="pending",
                    created_at=datetime.now(UTC),
                )
            ]
        )
        store.write_pending_questions(pq)

        llm = AsyncMock()
        llm.chat = AsyncMock(
            return_value=LLMResponse(content="Who was with you at the park?", model="m", usage={})
        )
        messaging = AsyncMock()
        messaging.broadcast_text = AsyncMock(
            return_value=[SendResult(success=True, message_id="msg_2")]
        )

        mgr = QuestionManager(store, llm, "m", messaging)
        count = await mgr.process_pending()

        assert count == 1
        llm.chat.assert_called_once()

    async def test_skips_non_pending(self, data_dir):
        store = DataStore(data_dir)
        store.initialize()

        pq = PendingQuestionsFile(
            questions=[
                PendingQuestion(
                    id="q_003",
                    type="memory_enrichment",
                    subject="test",
                    question="Already asked?",
                    status="asked",
                    created_at=datetime.now(UTC),
                )
            ]
        )
        store.write_pending_questions(pq)

        llm = AsyncMock()
        messaging = AsyncMock()

        mgr = QuestionManager(store, llm, "m", messaging)
        count = await mgr.process_pending()

        assert count == 0
        messaging.broadcast_text.assert_not_called()

    async def test_handles_send_failure(self, data_dir):
        store = DataStore(data_dir)
        store.initialize()

        pq = PendingQuestionsFile(
            questions=[
                PendingQuestion(
                    id="q_004",
                    type="memory_enrichment",
                    subject="test",
                    question="Test question?",
                    status="pending",
                    created_at=datetime.now(UTC),
                )
            ]
        )
        store.write_pending_questions(pq)

        llm = AsyncMock()
        messaging = AsyncMock()
        messaging.broadcast_text = AsyncMock(
            return_value=[SendResult(success=False, error="Connection failed")]
        )

        mgr = QuestionManager(store, llm, "m", messaging)
        count = await mgr.process_pending()

        assert count == 0
        # Status should remain pending
        updated = store.read_pending_questions()
        assert updated.questions[0].status == "pending"
