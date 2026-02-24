"""Parse free-text messages into Event models via LLM."""

import logging
import uuid
from datetime import date
from typing import Any

import yaml

from elephant.data.models import Event, MediaLinks
from elephant.llm.client import LLMClient
from elephant.llm.prompts import parse_event, parse_events_batch
from elephant.messaging.base import Attachment

logger = logging.getLogger(__name__)


async def parse_event_from_text(
    text: str,
    llm: LLMClient,
    model: str,
    context: dict[str, Any],
    source: str = "WhatsApp",
    event_date: date | None = None,
    attachments: list[Attachment] | None = None,
) -> Event:
    """Use LLM to parse free text into a structured Event."""
    messages = parse_event(text, context)
    response = await llm.chat(messages, model=model, temperature=0.3)

    parsed = yaml.safe_load(response.content or "")
    if not isinstance(parsed, dict):
        msg = f"LLM returned non-dict: {type(parsed).__name__}"
        raise ValueError(msg)

    today = event_date or date.today()
    slug = _slugify(parsed.get("title", "event"))
    event_id = f"{today.strftime('%Y%m%d')}_{slug}"

    # Build media from attachments
    media = None
    if attachments:
        photos = [a.file_path for a in attachments if a.media_type == "photo"]
        videos = [a.file_path for a in attachments if a.media_type == "video"]
        if photos or videos:
            media = MediaLinks(photos=photos, videos=videos)

    raw_time = parsed.get("time")

    return Event(
        id=event_id,
        date=today,
        time=str(raw_time) if raw_time is not None else None,
        title=parsed.get("title", text[:50]),
        type=parsed.get("type", "other"),
        description=parsed.get("description", text),
        people=parsed.get("people", []),
        location=parsed.get("location"),
        media=media,
        source=source,
        nostalgia_score=float(parsed.get("nostalgia_score", 1.0)),
        tags=parsed.get("tags", []),
    )


async def parse_events_from_document(
    caption: str,
    document_content: str,
    llm: LLMClient,
    model: str,
    context: dict[str, Any],
    source: str = "Telegram",
    attachments: list[Attachment] | None = None,
) -> list[Event]:
    """Parse a document's contents into multiple Event objects via LLM."""
    messages = parse_events_batch(caption, document_content, context)
    response = await llm.chat(messages, model=model, temperature=0.3)

    parsed = yaml.safe_load(response.content or "")

    # If LLM returned a single dict, wrap it in a list
    if isinstance(parsed, dict):
        parsed = [parsed]

    if not isinstance(parsed, list):
        msg = f"LLM returned unexpected type: {type(parsed).__name__}"
        raise ValueError(msg)

    # Build media from attachments (shared across all events from this doc)
    media = None
    if attachments:
        photos = [a.file_path for a in attachments if a.media_type == "photo"]
        videos = [a.file_path for a in attachments if a.media_type == "video"]
        if photos or videos:
            media = MediaLinks(photos=photos, videos=videos)

    events: list[Event] = []
    for item in parsed:
        if not isinstance(item, dict):
            logger.warning("Skipping non-dict item in batch parse: %s", type(item).__name__)
            continue

        # Parse date from the item, falling back to today
        event_date = date.today()
        raw_date = item.get("date")
        if raw_date:
            if isinstance(raw_date, date):
                event_date = raw_date
            elif isinstance(raw_date, str):
                try:
                    event_date = date.fromisoformat(raw_date)
                except ValueError:
                    logger.warning("Unparseable date '%s', using today", raw_date)

        slug = _slugify(item.get("title", "event"))
        event_id = f"{event_date.strftime('%Y%m%d')}_{slug}"

        raw_time = item.get("time")
        events.append(
            Event(
                id=event_id,
                date=event_date,
                time=str(raw_time) if raw_time is not None else None,
                title=item.get("title", "Untitled"),
                type=item.get("type", "other"),
                description=item.get("description", ""),
                people=item.get("people", []),
                location=item.get("location"),
                media=media,
                source=source,
                nostalgia_score=float(item.get("nostalgia_score", 1.0)),
                tags=item.get("tags", []),
            )
        )

    return events


def _slugify(text: str) -> str:
    """Convert text to a filename-safe slug."""
    slug = text.lower().strip()
    slug = "".join(c if c.isalnum() or c == " " else "" for c in slug)
    slug = "_".join(slug.split())
    if not slug:
        slug = f"event_{uuid.uuid4().hex[:6]}"
    return slug[:40]
