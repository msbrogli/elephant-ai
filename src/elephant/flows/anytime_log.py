"""Anytime message handler: resolve intent, route to appropriate flow."""

from __future__ import annotations

import base64
import logging
from typing import TYPE_CHECKING, Any

from elephant.brain.clarification import process_answer
from elephant.brain.feedback import process_feedback
from elephant.context_resolver import Intent, resolve_intent
from elephant.data.models import RawMessage, RawMessageAttachment
from elephant.llm.prompts import describe_image
from elephant.memory_parser import parse_memories_from_document
from elephant.tools.agent import ConversationalAgent

if TYPE_CHECKING:
    from elephant.data.store import DataStore
    from elephant.git_ops import GitRepo
    from elephant.llm.client import LLMClient
    from elephant.messaging.base import IncomingMessage, MessagingClient

logger = logging.getLogger(__name__)


class AnytimeLogFlow:
    """Routes incoming messages to the appropriate handler based on intent."""

    def __init__(
        self,
        store: DataStore,
        llm: LLMClient,
        parsing_model: str,
        messaging: MessagingClient,
        git: GitRepo,
        history_limit: int = 500,
    ) -> None:
        self._store = store
        self._llm = llm
        self._parsing_model = parsing_model
        self._messaging = messaging
        self._git = git
        self._agent = ConversationalAgent(
            store, llm, parsing_model, git, history_limit=history_limit,
        )

    async def handle_message(self, message: IncomingMessage) -> None:
        """Main entry point for all incoming messages."""
        logger.info("Received message from %s: %s", message.sender, message.text[:80])

        raw = RawMessage(
            text=message.text,
            sender=message.sender,
            message_id=message.message_id,
            timestamp=message.timestamp,
            reply_to_id=message.reply_to_id,
            attachments=[
                RawMessageAttachment(file_path=a.file_path, media_type=a.media_type)
                for a in message.attachments
            ],
        )
        self._store.append_raw_message(raw)

        await self._messaging.send_chat_action()

        digest_state = self._store.read_digest_state()
        pending_questions = self._store.read_pending_questions()

        intent = await resolve_intent(
            message,
            digest_state,
            pending_questions,
            llm=self._llm,
            model=self._parsing_model,
        )

        logger.info("Resolved intent: %s", intent.value)

        if intent == Intent.DIGEST_FEEDBACK:
            await self._handle_digest_feedback(message, digest_state.last_digest_memory_ids)
        elif intent == Intent.ANSWER_TO_QUESTION:
            await self._handle_answer(message, pending_questions)
        else:
            # NEW_MEMORY, CONTEXT_UPDATE, and anything else → conversational agent
            await self._handle_with_agent(message)

    async def _handle_with_agent(self, message: IncomingMessage) -> None:
        """Route message through the conversational agent."""
        source = "Telegram" if message.sender.isdigit() else "WhatsApp"

        # Check for document attachments — keep batch parse flow
        if message.attachments:
            doc_attachments = [a for a in message.attachments if a.media_type == "document"]
            if doc_attachments:
                await self._handle_document_memories(message, doc_attachments, source)
                return

        text = message.text

        # If there are photo attachments but no text, use vision to describe the image
        if not text and message.attachments:
            photo_attachments = [a for a in message.attachments if a.media_type == "photo"]
            if photo_attachments:
                people = self._store.read_all_people()
                prefs = self._store.read_preferences()
                try:
                    with open(photo_attachments[0].file_path, "rb") as f:
                        image_b64 = base64.b64encode(f.read()).decode()
                    messages = describe_image(image_b64, people, prefs)
                    response = await self._llm.chat(
                        messages, model=self._parsing_model, temperature=0.5
                    )
                    text = response.content or "Photo shared"
                    text = text.strip()
                    logger.info("Generated image description: %s", text[:80])
                except Exception:
                    logger.warning("Failed to describe image, using fallback text", exc_info=True)
                    text = "Photo shared"

        response_text = await self._agent.handle(
            text, source, attachments=message.attachments or None,
            message_id=message.message_id,
        )
        await self._messaging.send_text(response_text)

    _MAX_DOCUMENT_SIZE = 100_000  # ~100 KB limit for document content

    async def _handle_document_memories(
        self,
        message: IncomingMessage,
        doc_attachments: list[Any],
        source: str,
    ) -> None:
        """Read document files and parse batch memories from their contents."""
        # Read the first document attachment
        doc_path = doc_attachments[0].file_path
        try:
            with open(doc_path) as f:
                content = f.read(self._MAX_DOCUMENT_SIZE)
        except Exception:
            logger.warning("Failed to read document %s", doc_path, exc_info=True)
            await self._messaging.send_text("Sorry, I couldn't read that file.")
            return

        if not content.strip():
            await self._messaging.send_text("The file appears to be empty.")
            return

        caption = message.text or "Parse the memories from this file."

        people = self._store.read_all_people()
        prefs = self._store.read_preferences()

        try:
            memories = await parse_memories_from_document(
                caption=caption,
                document_content=content,
                llm=self._llm,
                model=self._parsing_model,
                people=people,
                prefs=prefs,
                source=source,
                attachments=message.attachments or None,
            )
        except Exception:
            logger.warning("Batch parse failed, falling back to agent", exc_info=True)
            # Fall back to conversational agent
            response_text = await self._agent.handle(
                caption, source, attachments=message.attachments or None,
                message_id=message.message_id,
            )
            await self._messaging.send_text(response_text)
            return

        if not memories:
            await self._messaging.send_text("I couldn't find any memories in that file.")
            return

        for memory in memories:
            memory.source_message_ids = [message.message_id]
            path = self._store.write_memory(memory)
            self._git.auto_commit("memory", memory.title, timestamp=memory.date, paths=[path])

        titles = "\n".join(f"- {m.title} ({m.date})" for m in memories[:10])
        summary = f"Got it! Logged {len(memories)} memories from your file.\n\n{titles}"
        if len(memories) > 10:
            summary += f"\n...and {len(memories) - 10} more."
        await self._messaging.send_text(summary)

    async def _handle_digest_feedback(
        self, message: IncomingMessage, memory_ids: list[str]
    ) -> None:
        """Process feedback on a digest."""
        sentiment = await process_feedback(
            message.text,
            memory_ids,
            self._llm,
            self._parsing_model,
            self._store,
            self._git,
        )
        responses = {
            "positive": "Glad you enjoyed it!",
            "negative": "Thanks for the feedback, I'll adjust.",
            "neutral": "Noted!",
        }
        await self._messaging.send_text(responses.get(sentiment, "Noted!"))

    async def _handle_answer(
        self, message: IncomingMessage, pending_questions: Any
    ) -> None:
        """Process an answer to a pending question."""
        # Find the question this is answering
        for q in pending_questions.questions:
            if q.status == "asked" and q.message_id and message.reply_to_id == q.message_id:
                success = await process_answer(
                    q.id,
                    message.text,
                    self._llm,
                    self._parsing_model,
                    self._store,
                )
                if success:
                    self._git.auto_commit("enrichment", f"Answer to {q.id}")
                    await self._messaging.send_text("Thanks! I've updated the memory.")
                return

        # Fallback: treat via agent
        await self._handle_with_agent(message)
