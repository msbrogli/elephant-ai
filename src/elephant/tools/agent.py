"""Conversational agent with LLM tool-calling loop."""

from __future__ import annotations

import json
import logging
from datetime import date
from typing import TYPE_CHECKING, Any

from elephant.llm.prompts import conversational_system_prompt
from elephant.tools.definitions import TOOL_DEFINITIONS, UPDATE_TOOLS
from elephant.tools.executor import ToolExecutor
from elephant.tracing import LLMCallStep, ToolExecStep, record_step

if TYPE_CHECKING:
    from elephant.data.store import DataStore
    from elephant.git_ops import GitRepo
    from elephant.llm.client import LLMClient

logger = logging.getLogger(__name__)


def _needs_reprompt(final_text: str, tools_called: set[str]) -> bool:
    """True if the LLM should be re-prompted to call an update tool or rephrase."""
    if tools_called & UPDATE_TOOLS:
        return False  # An update tool was called — all good
    return "no update needed" not in final_text.lower()


def _sanitize_msg(msg: dict[str, Any]) -> dict[str, Any]:
    """Return a JSON-safe copy of a message dict for trace storage."""
    out: dict[str, Any] = {"role": msg.get("role", "")}
    if "content" in msg:
        content = msg["content"]
        if isinstance(content, str):
            out["content"] = content[:2000]
        else:
            out["content"] = content
    if "tool_calls" in msg:
        out["tool_calls"] = msg["tool_calls"]
    if "tool_call_id" in msg:
        out["tool_call_id"] = msg["tool_call_id"]
    return out


class ConversationalAgent:
    """Agent that handles messages via LLM tool-calling loop."""

    MAX_TOOL_ROUNDS = 5
    MAX_ERROR_RETRIES = 3

    def __init__(
        self,
        store: DataStore,
        llm: LLMClient,
        model: str,
        git: GitRepo,
        history_limit: int = 500,
        verify_traces: bool = False,
    ) -> None:
        self._store = store
        self._llm = llm
        self._model = model
        self._executor = ToolExecutor(store, git, llm, model)
        self._history_limit = history_limit
        self._verify_traces = verify_traces

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

        consecutive_errors = 0
        tools_called: set[str] = set()
        tool_results_log: list[dict[str, str]] = []
        re_prompted = False

        for _round in range(self.MAX_TOOL_ROUNDS):
            response = await self._llm.chat_with_tools(
                messages,
                model=self._model,
                tools=TOOL_DEFINITIONS,
                temperature=0.4,
                max_tokens=1024,
            )

            record_step(LLMCallStep(
                method="chat_with_tools",
                model=self._model,
                temperature=0.4,
                max_tokens=1024,
                messages=[_sanitize_msg(m) for m in messages],
                response_content=response.content,
                response_tool_calls=[
                    {"id": tc.id, "function_name": tc.function_name, "arguments": tc.arguments}
                    for tc in response.tool_calls
                ],
                usage=response.usage,
            ))

            if not response.tool_calls:
                final_text = response.content or "Done!"

                if not re_prompted and _needs_reprompt(final_text, tools_called):
                    re_prompted = True
                    logger.warning("No update tool called and no opt-out, re-prompting")
                    messages.append({"role": "assistant", "content": final_text})
                    messages.append({
                        "role": "user",
                        "content": (
                            "[SYSTEM] You did not call any update tool and did not say "
                            "'No update needed.' If the user shared information that "
                            "should be stored, call the appropriate tool now "
                            "(update_person, create_memory, etc.). Otherwise, rephrase "
                            "your response and include 'No update needed.' at the end."
                        ),
                    })
                    continue

                if self._verify_traces:
                    corrected = await self._verify_trace(
                        user_content, final_text, tools_called, tool_results_log,
                    )
                    if corrected is not None:
                        final_text = corrected

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

            # Execute each tool call and collect results
            round_results: list[str] = []
            for tc in response.tool_calls:
                logger.info("Executing tool: %s(%s)", tc.function_name, tc.arguments[:100])
                # Record the step *before* execution so that any child
                # steps (e.g. git_commit) appear after it in the trace.
                step = ToolExecStep(
                    tool_call_id=tc.id,
                    function_name=tc.function_name,
                    arguments=tc.arguments,
                )
                record_step(step)
                result = await self._executor.execute(tc)
                step.result = result
                round_results.append(result)
                tools_called.add(tc.function_name)
                tool_results_log.append({
                    "tool": tc.function_name,
                    "args": tc.arguments[:200],
                    "result": result[:200],
                })
                messages.append({
                    "role": "tool",
                    "tool_call_id": tc.id,
                    "content": result,
                })

            # Track consecutive all-error rounds
            all_failed = all('"error"' in r for r in round_results)
            if all_failed:
                consecutive_errors += 1
                if consecutive_errors >= self.MAX_ERROR_RETRIES:
                    last_errors = [
                        json.loads(r).get("error", "Unknown error")
                        for r in round_results
                    ]
                    error_summary = "; ".join(last_errors)
                    final_text = (
                        f"I tried several times but couldn't complete the operation. "
                        f"Error: {error_summary}"
                    )
                    self._store.append_chat_history(user_content, final_text)
                    return final_text
            else:
                consecutive_errors = 0

        # Safety: if we hit max rounds, get a final response without tools
        response = await self._llm.chat(messages, model=self._model)
        record_step(LLMCallStep(
            method="chat",
            model=self._model,
            messages=[_sanitize_msg(m) for m in messages],
            response_content=response.content,
            usage=response.usage,
        ))
        final_text = response.content or "Done!"

        if self._verify_traces:
            corrected = await self._verify_trace(
                user_content, final_text, tools_called, tool_results_log,
            )
            if corrected is not None:
                final_text = corrected

        self._store.append_chat_history(user_content, final_text)
        return final_text

    async def _verify_trace(
        self,
        user_message: str,
        final_text: str,
        tools_called: set[str],
        tool_results_log: list[dict[str, str]],
    ) -> str | None:
        """Post-response QA audit. Returns corrected text or None if OK."""
        tools_summary = "\n".join(
            f"- {entry['tool']}({entry['args']}) -> {entry['result']}"
            for entry in tool_results_log
        ) or "(no tools called)"

        audit_prompt = (
            "You are a QA auditor for a family memory assistant. Review this interaction "
            "and check for:\n"
            "1. The assistant claims to have saved/updated data but no update tool was called.\n"
            "2. The response contradicts tool results.\n"
            "3. The user shared storable information that was not stored.\n\n"
            f"User message: {user_message[:500]}\n\n"
            f"Tools called:\n{tools_summary}\n\n"
            f"Assistant response: {final_text[:500]}\n\n"
            "If there is a problem, respond with a corrected assistant response. "
            "If everything is fine, respond with exactly: OK"
        )

        try:
            response = await self._llm.chat(
                [{"role": "user", "content": audit_prompt}],
                model=self._model,
                temperature=0.0,
                max_tokens=300,
            )
            result = (response.content or "").strip()
            if result == "OK":
                return None
            logger.warning("Trace verifier flagged issue, correcting response")
            return result
        except Exception:
            logger.warning("Trace verifier failed, keeping original response", exc_info=True)
            return None
