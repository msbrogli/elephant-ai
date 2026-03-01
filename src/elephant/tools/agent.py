"""Conversational agent with LLM tool-calling loop."""

from __future__ import annotations

import logging
from datetime import date
from typing import TYPE_CHECKING, Any

from elephant.llm.prompts import conversational_system_prompt
from elephant.tools.definitions import TOOL_DEFINITIONS
from elephant.tools.executor import ToolExecutor

if TYPE_CHECKING:
    from elephant.data.store import DataStore
    from elephant.git_ops import GitRepo
    from elephant.llm.client import LLMClient

logger = logging.getLogger(__name__)


class ConversationalAgent:
    """Agent that handles messages via LLM tool-calling loop."""

    MAX_TOOL_ROUNDS = 5

    def __init__(
        self,
        store: DataStore,
        llm: LLMClient,
        model: str,
        git: GitRepo,
        history_limit: int = 500,
    ) -> None:
        self._store = store
        self._llm = llm
        self._model = model
        self._executor = ToolExecutor(store, git, llm, model)
        self._history_limit = history_limit

    async def handle(
        self,
        user_message: str,
        source: str,
        attachments: list[Any] | None = None,
        message_id: str | None = None,
    ) -> str:
        """Process a user message through the tool-calling loop. Returns the final text."""
        self._executor.set_message_context(message_id=message_id)
        people = self._store.read_all_people()
        prefs = self._store.read_preferences()
        today = date.today().isoformat()

        last_contacts = self._store.get_latest_memory_dates_for_people(
            [p.display_name for p in people],
        )
        system_prompt = conversational_system_prompt(
            people, prefs, today, last_contacts=last_contacts,
        )

        # Build user content
        user_content = user_message
        if attachments:
            media_note = ", ".join(
                f"{a.media_type}: {a.file_path}" for a in attachments
            )
            user_content += f"\n\n[Attachments: {media_note}]"

        messages: list[dict[str, Any]] = [
            {"role": "system", "content": system_prompt},
        ]

        # Inject conversation history
        history = self._store.read_chat_history()
        for entry in history.entries[-self._history_limit :]:
            messages.append({"role": entry.role, "content": entry.content})

        messages.append({"role": "user", "content": user_content})

        for _round in range(self.MAX_TOOL_ROUNDS):
            response = await self._llm.chat_with_tools(
                messages,
                model=self._model,
                tools=TOOL_DEFINITIONS,
                temperature=0.7,
                max_tokens=1024,
            )

            if not response.tool_calls:
                # LLM returned a text response — we're done
                final_text = response.content or "Done!"
                self._store.append_chat_history(user_content, final_text)
                return final_text

            # Append assistant message with tool calls
            assistant_msg: dict[str, Any] = {
                "role": "assistant",
                "tool_calls": [
                    {
                        "id": tc.id,
                        "type": "function",
                        "function": {
                            "name": tc.function_name,
                            "arguments": tc.arguments,
                        },
                    }
                    for tc in response.tool_calls
                ],
            }
            if response.content:
                assistant_msg["content"] = response.content
            messages.append(assistant_msg)

            # Execute each tool call and append results
            for tc in response.tool_calls:
                logger.info("Executing tool: %s(%s)", tc.function_name, tc.arguments[:100])
                result = await self._executor.execute(tc)
                messages.append({
                    "role": "tool",
                    "tool_call_id": tc.id,
                    "content": result,
                })

        # Safety: if we hit max rounds, get a final response without tools
        response = await self._llm.chat(messages, model=self._model)
        final_text = response.content or "Done!"
        self._store.append_chat_history(user_content, final_text)
        return final_text
