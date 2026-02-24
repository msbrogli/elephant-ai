"""Generate follow-up questions for thin events and process answers."""

import logging
import uuid
from datetime import UTC, datetime
from typing import Any

from elephant.data.models import Event, PendingQuestion
from elephant.data.store import DataStore
from elephant.llm.client import LLMClient
from elephant.llm.prompts import enrich_event, generate_clarification

logger = logging.getLogger(__name__)

MAX_PENDING_QUESTIONS = 2
THIN_EVENT_THRESHOLD = 50  # chars in description


def is_thin_event(event: Event) -> bool:
    """Check if an event is too thin and needs enrichment."""
    short_desc = len(event.description) < THIN_EVENT_THRESHOLD
    few_people = len(event.people) <= 1
    no_location = event.location is None
    return short_desc and (few_people or no_location)


async def generate_question_for_event(
    event: Event,
    llm: LLMClient,
    model: str,
    context: dict[str, Any],
    store: DataStore,
) -> PendingQuestion | None:
    """Generate a follow-up question for a thin event, if under rate limit."""
    pq = store.read_pending_questions()
    pending_count = sum(1 for q in pq.questions if q.status in ("pending", "asked"))
    if pending_count >= MAX_PENDING_QUESTIONS:
        logger.debug("Rate limit: %d pending questions, skipping", pending_count)
        return None

    messages = generate_clarification(event.title, event.description, context)
    response = await llm.chat(messages, model=model, temperature=0.7)

    question = PendingQuestion(
        id=f"q_{uuid.uuid4().hex[:8]}",
        type="event_enrichment",
        subject=event.id,
        question=(response.content or "").strip(),
        status="pending",
        created_at=datetime.now(UTC),
    )

    pq.questions.append(question)
    store.write_pending_questions(pq)
    logger.info("Generated question %s for event %s", question.id, event.id)
    return question


async def process_answer(
    question_id: str,
    answer_text: str,
    llm: LLMClient,
    model: str,
    store: DataStore,
) -> bool:
    """Process user's answer to a clarification question."""
    pq = store.read_pending_questions()
    question = None
    for q in pq.questions:
        if q.id == question_id:
            question = q
            break

    if question is None:
        logger.warning("Question %s not found", question_id)
        return False

    if question.type != "event_enrichment":
        logger.info("Question %s is type %s, not event_enrichment", question_id, question.type)
        question.status = "answered"
        question.answer = answer_text
        question.answered_at = datetime.now(UTC)
        store.write_pending_questions(pq)
        return True

    # Find the event
    event_id = question.subject
    if len(event_id) >= 8 and event_id[:8].isdigit():
        from datetime import date as _date

        y, m, d = int(event_id[:4]), int(event_id[4:6]), int(event_id[6:8])
        slug = event_id[9:] if len(event_id) > 9 else event_id
        path = store._event_path(_date(y, m, d), slug)
        try:
            event = store.read_event(path)
        except FileNotFoundError:
            logger.warning("Event %s not found for question %s", event_id, question_id)
            return False

        # Enrich the event description via LLM
        messages = enrich_event(
            event.title,
            event.description,
            question.question or "",
            answer_text,
        )
        response = await llm.chat(messages, model=model, temperature=0.3)
        enriched_desc = (response.content or "").strip()

        # Update event
        updated = event.model_copy(update={"description": enriched_desc})
        store.write_event(updated)
        logger.info("Enriched event %s with answer to %s", event_id, question_id)

    # Mark question as answered
    question.status = "answered"
    question.answer = answer_text
    question.answered_at = datetime.now(UTC)
    store.write_pending_questions(pq)
    return True
