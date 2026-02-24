"""Tests for anytime log flow: intent routing, all branches."""

from datetime import UTC, datetime, timedelta
from unittest.mock import AsyncMock, MagicMock

import pytest

from elephant.data.models import (
    DigestState,
    PendingQuestion,
    PendingQuestionsFile,
)
from elephant.data.store import DataStore
from elephant.flows.anytime_log import AnytimeLogFlow
from elephant.git_ops import GitRepo
from elephant.llm.client import LLMResponse
from elephant.messaging.base import Attachment, IncomingMessage, SendResult


def _make_message(text="test", reply_to_id=None, timestamp=None):
    return IncomingMessage(
        text=text,
        sender="456",
        message_id="msg_1",
        timestamp=timestamp or datetime.now(UTC),
        reply_to_id=reply_to_id,
    )


@pytest.fixture
def flow_deps(data_dir):
    """Create all dependencies for AnytimeLogFlow."""
    store = DataStore(data_dir)
    store.initialize()

    llm = AsyncMock()
    llm.chat = AsyncMock(
        return_value=LLMResponse(
            content=(
                "title: Park day\ntype: daily\n"
                "description: Went to the park with Lily\n"
                "people:\n  - Lily\ntags: []"
            ),
            model="m",
            usage={},
        )
    )
    # Default chat_with_tools returns a text response (agent just chats)
    llm.chat_with_tools = AsyncMock(
        return_value=LLMResponse(
            content="Got it! I've logged that memory.",
            model="m",
            usage={},
            tool_calls=[],
        )
    )

    messaging = AsyncMock()
    messaging.send_text = AsyncMock(
        return_value=SendResult(success=True, message_id="msg_reply")
    )
    messaging.broadcast_text = AsyncMock(
        return_value=[SendResult(success=True, message_id="msg_broadcast")]
    )
    messaging.send_chat_action = AsyncMock()

    git = MagicMock(spec=GitRepo)
    git.auto_commit = MagicMock(return_value="abc123")

    flow = AnytimeLogFlow(store, llm, "test-model", messaging, git)
    return flow, store, llm, messaging, git


class TestAnytimeLogFlow:
    async def test_new_event_routes_to_agent(self, flow_deps):
        flow, store, llm, messaging, git = flow_deps

        msg = _make_message("We went to the park with Lily today")
        await flow.handle_message(msg)

        messaging.send_text.assert_called()
        # Agent was called (chat_with_tools)
        llm.chat_with_tools.assert_called()

    async def test_context_update_routes_to_agent(self, flow_deps):
        flow, store, llm, messaging, git = flow_deps

        # Make intent classification return context_update
        call_count = 0

        async def mock_chat(messages, model, **kwargs):
            nonlocal call_count
            call_count += 1
            if call_count == 1:
                # Intent classification
                return LLMResponse(content="context_update", model="m", usage={})
            # Shouldn't reach here for old handler path
            return LLMResponse(content="test", model="m", usage={})

        llm.chat = AsyncMock(side_effect=mock_chat)

        now = datetime.now(UTC)
        msg = _make_message("My daughter Lily was born on Jan 10", timestamp=now)
        await flow.handle_message(msg)

        messaging.send_text.assert_called()
        # Agent was invoked (chat_with_tools), not the old context handler
        llm.chat_with_tools.assert_called()

    async def test_digest_feedback_by_reply(self, flow_deps):
        flow, store, llm, messaging, git = flow_deps

        # Set up digest state
        state = DigestState(
            last_digest_sent_at=datetime.now(UTC),
            last_digest_event_ids=["20260224_test"],
            last_digest_message_id="digest_msg_1",
        )
        store.write_digest_state(state)

        # Mock sentiment classification
        llm.chat = AsyncMock(
            return_value=LLMResponse(content="positive", model="m", usage={})
        )

        msg = _make_message("Love it!", reply_to_id="digest_msg_1")
        await flow.handle_message(msg)

        messaging.send_text.assert_called()
        call_text = messaging.send_text.call_args[0][0]
        assert any(w in call_text for w in ("Glad", "Noted", "feedback", "enjoy"))

    async def test_digest_feedback_by_timing(self, flow_deps):
        flow, store, llm, messaging, git = flow_deps

        now = datetime.now(UTC)
        state = DigestState(
            last_digest_sent_at=now - timedelta(minutes=5),
            last_digest_event_ids=["20260224_test"],
        )
        store.write_digest_state(state)

        llm.chat = AsyncMock(
            return_value=LLMResponse(content="neutral", model="m", usage={})
        )

        msg = _make_message("ok", timestamp=now)
        await flow.handle_message(msg)

        messaging.send_text.assert_called()

    async def test_answer_to_question(self, flow_deps):
        flow, store, llm, messaging, git = flow_deps

        # Create an event and a question
        from datetime import date

        from elephant.data.models import Event

        event = Event(
            id="20260224_park_day",
            date=date(2026, 2, 24),
            title="Park day",
            type="daily",
            description="Went to park",
            people=[],
            source="WhatsApp",
        )
        store.write_event(event)

        pq = PendingQuestionsFile(
            questions=[
                PendingQuestion(
                    id="q_001",
                    type="event_enrichment",
                    subject="20260224_park_day",
                    question="Who was there?",
                    status="asked",
                    created_at=datetime.now(UTC),
                )
            ]
        )
        store.write_pending_questions(pq)

        llm.chat = AsyncMock(
            return_value=LLMResponse(
                content="Went to the park with Lily and had a great time on the swings.",
                model="m",
                usage={},
            )
        )

        msg = _make_message("Lily came with me", reply_to_id="q_001")
        await flow.handle_message(msg)

        messaging.send_text.assert_called()

    async def test_document_triggers_batch_parse(self, flow_deps, tmp_path):
        flow, store, llm, messaging, git = flow_deps

        # Create a temp JSON file to simulate a document attachment
        doc_file = tmp_path / "calendar.json"
        doc_file.write_text('[{"name":"Mom birthday","due":"2026-03-15"}]')

        call_count = 0

        async def mock_chat(messages, model, **kwargs):
            nonlocal call_count
            call_count += 1
            if call_count == 1:
                # Intent classification
                return LLMResponse(content="new_event", model="m", usage={})
            else:
                # Batch parse
                return LLMResponse(
                    content=(
                        "- title: Mom's birthday\n"
                        "  type: celebration\n"
                        "  date: 2026-03-15\n"
                        "  description: Mom's birthday\n"
                        "  people: [Mom]\n"
                        "  location: null\n"
                        "  nostalgia_score: 1.5\n"
                        "  tags: [birthday]\n"
                    ),
                    model="m",
                    usage={},
                )

        llm.chat = AsyncMock(side_effect=mock_chat)

        msg = IncomingMessage(
            text="These are birthdays from a calendar export",
            sender="456",
            message_id="msg_doc",
            timestamp=datetime.now(UTC),
            attachments=[Attachment(file_path=str(doc_file), media_type="document")],
        )
        await flow.handle_message(msg)

        call_text = messaging.send_text.call_args[0][0]
        assert "1 events" in call_text or "Logged 1" in call_text
        assert "Mom's birthday" in call_text
