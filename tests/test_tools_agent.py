"""Tests for the conversational agent tool-calling loop."""

import json
from datetime import date
from unittest.mock import AsyncMock, MagicMock

import pytest

from elephant.data.models import Event
from elephant.data.store import DataStore
from elephant.git_ops import GitRepo
from elephant.llm.client import LLMResponse, ToolCall
from elephant.tools.agent import ConversationalAgent


@pytest.fixture
def agent_deps(data_dir):
    store = DataStore(data_dir)
    store.initialize()

    llm = AsyncMock()
    git = MagicMock(spec=GitRepo)
    git.auto_commit = MagicMock(return_value="abc123")

    agent = ConversationalAgent(store, llm, "test-model", git)
    return agent, store, llm, git


class TestConversationalAgent:
    async def test_direct_text_response(self, agent_deps):
        """LLM responds with text, no tool calls."""
        agent, store, llm, git = agent_deps

        llm.chat_with_tools = AsyncMock(return_value=LLMResponse(
            content="Hello! How can I help you?",
            model="m",
            usage={},
            tool_calls=[],
        ))

        result = await agent.handle("Hello!", "Telegram")
        assert result == "Hello! How can I help you?"
        llm.chat_with_tools.assert_called_once()

    async def test_tool_call_then_text(self, agent_deps):
        """LLM makes a tool call, gets result, then responds with text."""
        agent, store, llm, git = agent_deps

        # Seed an event
        store.write_event(Event(
            id="20260224_park_day", date=date(2026, 2, 24), title="Park day",
            type="daily", description="Went to the park with Lily",
            people=["Lily"], source="agent",
        ))

        call_count = 0

        async def mock_chat_with_tools(messages, model, tools, **kwargs):
            nonlocal call_count
            call_count += 1
            if call_count == 1:
                # First call: LLM wants to search events
                return LLMResponse(
                    content=None,
                    model="m",
                    usage={},
                    tool_calls=[ToolCall(
                        id="tc_1",
                        function_name="list_events",
                        arguments=json.dumps({"date_from": "2026-02-24", "date_to": "2026-02-24"}),
                    )],
                )
            else:
                # Second call: LLM responds with summary
                return LLMResponse(
                    content="Today you went to the park with Lily!",
                    model="m",
                    usage={},
                    tool_calls=[],
                )

        llm.chat_with_tools = AsyncMock(side_effect=mock_chat_with_tools)

        result = await agent.handle("What happened today?", "Telegram")
        assert "park" in result.lower() or "Lily" in result
        assert call_count == 2

    async def test_create_event_tool_call(self, agent_deps):
        """LLM calls create_event, then confirms."""
        agent, store, llm, git = agent_deps

        call_count = 0

        async def mock_chat_with_tools(messages, model, tools, **kwargs):
            nonlocal call_count
            call_count += 1
            if call_count == 1:
                return LLMResponse(
                    content=None,
                    model="m",
                    usage={},
                    tool_calls=[ToolCall(
                        id="tc_1",
                        function_name="create_event",
                        arguments=json.dumps({
                            "title": "Park day",
                            "date": "2026-02-24",
                            "type": "outing",
                            "description": "We went to the park with Lily",
                            "people": ["Lily"],
                            "location": "Central Park",
                        }),
                    )],
                )
            else:
                return LLMResponse(
                    content="Got it! I've saved your park outing with Lily.",
                    model="m",
                    usage={},
                    tool_calls=[],
                )

        llm.chat_with_tools = AsyncMock(side_effect=mock_chat_with_tools)

        result = await agent.handle("We went to the park with Lily", "Telegram")
        assert "park" in result.lower() or "Lily" in result
        git.auto_commit.assert_called()  # Event was committed

    async def test_multiple_tool_calls(self, agent_deps):
        """LLM makes multiple tool calls in sequence."""
        agent, store, llm, git = agent_deps

        call_count = 0

        async def mock_chat_with_tools(messages, model, tools, **kwargs):
            nonlocal call_count
            call_count += 1
            if call_count == 1:
                return LLMResponse(
                    content=None, model="m", usage={},
                    tool_calls=[
                        ToolCall(id="tc_1", function_name="get_context", arguments="{}"),
                        ToolCall(id="tc_2", function_name="list_people", arguments="{}"),
                    ],
                )
            else:
                return LLMResponse(
                    content="Here's what I know about your family...",
                    model="m", usage={}, tool_calls=[],
                )

        llm.chat_with_tools = AsyncMock(side_effect=mock_chat_with_tools)

        result = await agent.handle("Tell me about my family", "Telegram")
        assert "family" in result.lower()

    async def test_max_rounds_safety(self, agent_deps):
        """Agent stops after MAX_TOOL_ROUNDS and falls back to plain chat."""
        agent, store, llm, git = agent_deps

        # Always return tool calls (infinite loop scenario)
        llm.chat_with_tools = AsyncMock(return_value=LLMResponse(
            content=None, model="m", usage={},
            tool_calls=[ToolCall(
                id="tc_1", function_name="list_events", arguments="{}",
            )],
        ))
        llm.chat = AsyncMock(return_value=LLMResponse(
            content="Sorry, I had trouble processing that.",
            model="m", usage={},
        ))

        result = await agent.handle("Do something", "Telegram")
        assert result == "Sorry, I had trouble processing that."
        assert llm.chat_with_tools.call_count == agent.MAX_TOOL_ROUNDS
        llm.chat.assert_called_once()
