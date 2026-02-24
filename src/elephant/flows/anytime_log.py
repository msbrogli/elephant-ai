"""Anytime message handler: resolve intent, route to appropriate flow."""

import base64
import logging
from typing import Any

from elephant.brain.clarification import process_answer
from elephant.brain.feedback import process_feedback
from elephant.context_resolver import Intent, resolve_intent
from elephant.data.store import DataStore
from elephant.event_parser import parse_events_from_document
from elephant.git_ops import GitRepo
from elephant.llm.client import LLMClient
from elephant.llm.prompts import describe_image
from elephant.messaging.base import IncomingMessage, MessagingClient
from elephant.tools.agent import ConversationalAgent

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
    ) -> None:
        self._store = store
        self._llm = llm
        self._parsing_model = parsing_model
        self._messaging = messaging
        self._git = git
        self._agent = ConversationalAgent(store, llm, parsing_model, git)

    async def handle_message(self, message: IncomingMessage) -> None:
        """Main entry point for all incoming messages."""
        logger.info("Received message from %s: %s", message.sender, message.text[:80])

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
            await self._handle_digest_feedback(message, digest_state.last_digest_event_ids)
        elif intent == Intent.ANSWER_TO_QUESTION:
            await self._handle_answer(message, pending_questions)
        else:
            # NEW_EVENT, CONTEXT_UPDATE, and anything else → conversational agent
            await self._handle_with_agent(message)

    async def _handle_with_agent(self, message: IncomingMessage) -> None:
        """Route message through the conversational agent."""
        source = "Telegram" if message.sender.isdigit() else "WhatsApp"

        # Check for document attachments — keep batch parse flow
        if message.attachments:
            doc_attachments = [a for a in message.attachments if a.media_type == "document"]
            if doc_attachments:
                context = self._store.read_context()
                await self._handle_document_events(message, doc_attachments, context, source)
                return

        text = message.text

        # If there are photo attachments but no text, use vision to describe the image
        if not text and message.attachments:
            photo_attachments = [a for a in message.attachments if a.media_type == "photo"]
            if photo_attachments:
                context = self._store.read_context()
                try:
                    with open(photo_attachments[0].file_path, "rb") as f:
                        image_b64 = base64.b64encode(f.read()).decode()
                    messages = describe_image(image_b64, context)
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
        )
        await self._messaging.send_text(response_text)

    _MAX_DOCUMENT_SIZE = 100_000  # ~100 KB limit for document content

    async def _handle_document_events(
        self,
        message: IncomingMessage,
        doc_attachments: list[Any],
        context: dict[str, Any],
        source: str,
    ) -> None:
        """Read document files and parse batch events from their contents."""
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

        caption = message.text or "Parse the events from this file."

        try:
            events = await parse_events_from_document(
                caption=caption,
                document_content=content,
                llm=self._llm,
                model=self._parsing_model,
                context=context,
                source=source,
                attachments=message.attachments or None,
            )
        except Exception:
            logger.warning("Batch parse failed, falling back to agent", exc_info=True)
            # Fall back to conversational agent
            response_text = await self._agent.handle(
                caption, source, attachments=message.attachments or None,
            )
            await self._messaging.send_text(response_text)
            return

        if not events:
            await self._messaging.send_text("I couldn't find any events in that file.")
            return

        for event in events:
            path = self._store.write_event(event)
            self._git.auto_commit("event", event.title, timestamp=event.date, paths=[path])

        titles = "\n".join(f"- {e.title} ({e.date})" for e in events[:10])
        summary = f"Got it! Logged {len(events)} events from your file.\n\n{titles}"
        if len(events) > 10:
            summary += f"\n...and {len(events) - 10} more."
        await self._messaging.send_text(summary)

    async def _handle_digest_feedback(
        self, message: IncomingMessage, event_ids: list[str]
    ) -> None:
        """Process feedback on a digest."""
        sentiment = await process_feedback(
            message.text,
            event_ids,
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
