"""Tests for conversation history persistence and injection."""

from unittest.mock import AsyncMock, MagicMock

import pytest

from elephant.data.models import ChatHistoryEntry, ChatHistoryFile
from elephant.data.store import DataStore
from elephant.git_ops import GitRepo
from elephant.llm.client import LLMResponse
from elephant.tools.agent import ConversationalAgent


@pytest.fixture
def store(data_dir):
    s = DataStore(data_dir)
    s.initialize()
    return s


class TestDataStoreChatHistory:
    def test_read_empty_chat_history(self, store):
        history = store.read_chat_history()
        assert history.entries == []

    def test_append_and_read(self, store):
        store.append_chat_history("hello", "hi there!")
        history = store.read_chat_history()
        assert len(history.entries) == 2
        assert history.entries[0].role == "user"
        assert history.entries[0].content == "hello"
        assert history.entries[1].role == "assistant"
        assert history.entries[1].content == "hi there!"

    def test_append_multiple(self, store):
        store.append_chat_history("msg1", "reply1")
        store.append_chat_history("msg2", "reply2")
        history = store.read_chat_history()
        assert len(history.entries) == 4
        assert history.entries[2].content == "msg2"
        assert history.entries[3].content == "reply2"

    def test_append_trims_to_max_entries(self, store):
        # Seed 10 entries (5 exchanges)
        for i in range(5):
            store.append_chat_history(f"user_{i}", f"bot_{i}")

        # Append with max_entries=4 — should keep only the last 4 entries
        store.append_chat_history("final_user", "final_bot", max_entries=4)

        history = store.read_chat_history()
        assert len(history.entries) == 4
        assert history.entries[0].content == "user_4"
        assert history.entries[1].content == "bot_4"
        assert history.entries[2].content == "final_user"
        assert history.entries[3].content == "final_bot"

    def test_write_and_read_roundtrip(self, store):
        from datetime import UTC, datetime

        now = datetime.now(UTC)
        history = ChatHistoryFile(entries=[
            ChatHistoryEntry(role="user", content="test", timestamp=now),
            ChatHistoryEntry(role="assistant", content="reply", timestamp=now),
        ])
        store.write_chat_history(history)

        loaded = store.read_chat_history()
        assert len(loaded.entries) == 2
        assert loaded.entries[0].content == "test"
        assert loaded.entries[1].content == "reply"


class TestAgentHistory:
    @pytest.fixture
    def agent_deps(self, data_dir):
        store = DataStore(data_dir)
        store.initialize()
        llm = AsyncMock()
        git = MagicMock(spec=GitRepo)
        git.auto_commit = MagicMock(return_value="abc123")
        agent = ConversationalAgent(store, llm, "test-model", git, history_limit=10)
        return agent, store, llm

    async def test_history_saved_after_response(self, agent_deps):
        agent, store, llm = agent_deps
        llm.chat_with_tools = AsyncMock(return_value=LLMResponse(
            content="I remember!", model="m", usage={}, tool_calls=[],
        ))

        await agent.handle("Remember this", "Telegram")

        history = store.read_chat_history()
        assert len(history.entries) == 2
        assert history.entries[0].role == "user"
        assert history.entries[0].content == "Remember this"
        assert history.entries[1].role == "assistant"
        assert history.entries[1].content == "I remember!"

    async def test_history_injected_into_messages(self, agent_deps):
        agent, store, llm = agent_deps

        # Seed history
        store.append_chat_history("previous question", "previous answer")

        llm.chat_with_tools = AsyncMock(return_value=LLMResponse(
            content="OK", model="m", usage={}, tool_calls=[],
        ))

        await agent.handle("new message", "Telegram")

        # Inspect the messages passed to the LLM
        call_args = llm.chat_with_tools.call_args
        messages = call_args[0][0]  # first positional arg

        # messages[0] = system prompt
        assert messages[0]["role"] == "system"
        # messages[1..2] = history (user + assistant)
        assert messages[1]["role"] == "user"
        assert messages[1]["content"] == "previous question"
        assert messages[2]["role"] == "assistant"
        assert messages[2]["content"] == "previous answer"
        # messages[3] = current user message
        assert messages[3]["role"] == "user"
        assert messages[3]["content"] == "new message"

    async def test_history_limit_respected(self, agent_deps):
        agent, store, llm = agent_deps
        # Agent has history_limit=10

        # Seed 20 entries (10 exchanges)
        for i in range(10):
            store.append_chat_history(f"u{i}", f"a{i}")

        llm.chat_with_tools = AsyncMock(return_value=LLMResponse(
            content="OK", model="m", usage={}, tool_calls=[],
        ))

        await agent.handle("latest", "Telegram")

        call_args = llm.chat_with_tools.call_args
        messages = call_args[0][0]

        # system + 10 history entries + 1 current user = 12 total
        assert len(messages) == 12
        # First history entry should be the 10th from the end of 20 entries
        assert messages[1]["content"] == "u5"

    async def test_empty_history_works(self, agent_deps):
        agent, store, llm = agent_deps
        llm.chat_with_tools = AsyncMock(return_value=LLMResponse(
            content="Hello!", model="m", usage={}, tool_calls=[],
        ))

        result = await agent.handle("hi", "Telegram")
        assert result == "Hello!"

        call_args = llm.chat_with_tools.call_args
        messages = call_args[0][0]
        # system + user = 2
        assert len(messages) == 2

    async def test_history_saved_after_max_rounds(self, agent_deps):
        agent, store, llm = agent_deps

        from elephant.llm.client import ToolCall

        llm.chat_with_tools = AsyncMock(return_value=LLMResponse(
            content=None, model="m", usage={},
            tool_calls=[ToolCall(
                id="tc_1", function_name="list_memories", arguments="{}",
            )],
        ))
        llm.chat = AsyncMock(return_value=LLMResponse(
            content="Fallback response", model="m", usage={},
        ))

        result = await agent.handle("do something", "Telegram")
        assert result == "Fallback response"

        history = store.read_chat_history()
        assert len(history.entries) == 2
        assert history.entries[0].content == "do something"
        assert history.entries[1].content == "Fallback response"
