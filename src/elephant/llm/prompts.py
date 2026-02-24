"""All prompt templates as functions returning message arrays."""

from __future__ import annotations

from typing import Any


def parse_event(text: str, context: dict[str, Any]) -> list[dict[str, str]]:
    """Prompt to parse free-text message into an event."""
    context_str = _format_context(context)
    return [
        {
            "role": "system",
            "content": (
                "You are a family memory assistant. Parse the user's message into a structured "
                "event. Respond ONLY with valid YAML (no markdown fencing).\n\n"
                "Required fields:\n"
                "  title: short title\n"
                "  type: milestone | daily | outing | celebration"
                " | health | travel | mundane | other\n"
                "  time: HH:MM or null (if a time is mentioned or can be inferred)\n"
                "  description: what happened\n"
                "  people: list of names\n"
                "  location: place or null\n"
                "  nostalgia_score: 0.5-2.0 (higher for milestones)\n"
                "  tags: list of relevant tags\n\n"
                f"Family context:\n{context_str}"
            ),
        },
        {"role": "user", "content": text},
    ]


def parse_events_batch(
    caption: str, document_content: str, context: dict[str, Any]
) -> list[dict[str, Any]]:
    """Prompt to parse document contents into multiple events."""
    context_str = _format_context(context)
    return [
        {
            "role": "system",
            "content": (
                "You are a family memory assistant. The user sent a file with structured data "
                "(JSON, CSV, etc.) containing multiple events. Parse the file contents into a "
                "YAML list of events.\n\n"
                "The user's caption describes how to interpret the data.\n\n"
                "Each item in the list must have:\n"
                "  title: short title\n"
                "  type: milestone | daily | outing | celebration"
                " | health | travel | mundane | other\n"
                "  date: YYYY-MM-DD (trust day/month from the data; if an item looks like a "
                "birthday and the year seems wrong, use the year as-is but note it "
                "in description)\n"
                "  time: HH:MM or null (if a time is present in the data)\n"
                "  description: what the event is about\n"
                "  people: list of names\n"
                "  location: place or null\n"
                "  nostalgia_score: 0.5-2.0\n"
                "  tags: list of relevant tags\n\n"
                "Respond ONLY with a valid YAML list (no markdown fencing). "
                "Example:\n"
                "- title: Mom's birthday\n"
                "  type: celebration\n"
                "  date: 2026-03-15\n"
                "  description: Mom's birthday\n"
                "  people: [Mom]\n"
                "  location: null\n"
                "  nostalgia_score: 1.5\n"
                "  tags: [birthday]\n\n"
                f"Family context:\n{context_str}"
            ),
        },
        {
            "role": "user",
            "content": (
                f"Caption/instructions: {caption}\n\n"
                f"File contents:\n{document_content}"
            ),
        },
    ]


def morning_digest(
    events: list[dict[str, Any]],
    context: dict[str, Any],
    tone_style: str = "heartfelt",
    tone_length: str = "short",
    birthdays: list[dict[str, Any]] | None = None,
) -> list[dict[str, str]]:
    """Prompt to generate a morning digest story."""
    context_str = _format_context(context)
    events_str = "\n---\n".join(
        f"Date: {e.get('date')}\nTitle: {e.get('title')}\n"
        f"Description: {e.get('description')}\nPeople: {e.get('people')}\n"
        f"Location: {e.get('location', 'N/A')}"
        for e in events
    )

    birthday_section = ""
    if birthdays:
        lines: list[str] = []
        for b in birthdays:
            name = b["name"]
            days = b["days_until"]
            if days == 0:
                lines.append(f"- TODAY is {name}'s birthday!")
            elif days <= 7:
                lines.append(f"- {name}'s birthday is in {days} days — finalize gift plans!")
            elif days <= 14:
                lines.append(
                    f"- {name}'s birthday is in {days} days — start thinking about a gift"
                )
            else:
                lines.append(f"- {name}'s birthday is coming up in {days} days")
        birthday_section = (
            "\n\nUpcoming birthdays (weave naturally into the message):\n"
            + "\n".join(lines)
        )

    system_content = (
        "You are a warm family storyteller. Generate a morning digest message about "
        "memories from this day in previous years. "
        f"Tone: {tone_style}. Length: {tone_length}.\n\n"
        "Write a natural, conversational message. Include the year each memory is from. "
        "If no events, write a brief encouraging note.\n\n"
        f"Family context:\n{context_str}"
        f"{birthday_section}"
    )

    user_content = (
        f"Today's memories from previous years:\n\n{events_str}"
        if events_str
        else "No memories found for today."
    )

    return [
        {"role": "system", "content": system_content},
        {"role": "user", "content": user_content},
    ]


def evening_checkin(context: dict[str, Any]) -> list[dict[str, str]]:
    """Prompt to generate an evening check-in message."""
    context_str = _format_context(context)
    return [
        {
            "role": "system",
            "content": (
                "You are a warm family assistant. Generate a brief, friendly evening check-in "
                "message asking the user what happened today worth remembering. "
                "Keep it short (1-2 sentences). Vary the phrasing each time.\n\n"
                f"Family context:\n{context_str}"
            ),
        },
        {"role": "user", "content": "Generate tonight's check-in prompt."},
    ]


def classify_intent(text: str, has_recent_digest: bool) -> list[dict[str, str]]:
    """Prompt to classify message intent when ambiguous."""
    digest_note = " A digest was recently sent." if has_recent_digest else ""
    return [
        {
            "role": "system",
            "content": (
                "Classify the user's message intent. Respond with ONLY one of these labels:\n"
                "- new_event: describing something that happened\n"
                "- digest_feedback: reacting to a digest (e.g. 'love it', 'too long', emoji)\n"
                "- context_update: sharing family info (e.g. 'my daughter is named Lily')\n"
                "- answer_to_question: answering a previously asked question\n\n"
                f"Context:{digest_note}"
            ),
        },
        {"role": "user", "content": text},
    ]


def classify_sentiment(text: str) -> list[dict[str, str]]:
    """Prompt to classify feedback sentiment."""
    return [
        {
            "role": "system",
            "content": (
                "Classify the sentiment of this digest feedback. "
                "Respond with ONLY one word: positive, neutral, or negative."
            ),
        },
        {"role": "user", "content": text},
    ]


def generate_clarification(
    event_title: str,
    event_description: str,
    context: dict[str, Any],
) -> list[dict[str, str]]:
    """Prompt to generate a follow-up question for a thin event."""
    context_str = _format_context(context)
    return [
        {
            "role": "system",
            "content": (
                "You are a family memory assistant. The user logged a brief event that lacks "
                "detail. Generate ONE short, friendly follow-up question to enrich the memory. "
                "Focus on: who was there, where it happened, or what made it special.\n\n"
                f"Family context:\n{context_str}"
            ),
        },
        {
            "role": "user",
            "content": f"Event: {event_title}\nDescription: {event_description}",
        },
    ]


def enrich_event(
    event_title: str,
    event_description: str,
    question: str,
    answer: str,
) -> list[dict[str, str]]:
    """Prompt to enrich an event with the user's answer to a follow-up question."""
    return [
        {
            "role": "system",
            "content": (
                "You are a family memory assistant. The user answered a follow-up question "
                "about an event. Generate an updated description that incorporates the new info. "
                "Respond with ONLY the updated description text."
            ),
        },
        {
            "role": "user",
            "content": (
                f"Original title: {event_title}\n"
                f"Original description: {event_description}\n"
                f"Question asked: {question}\n"
                f"User's answer: {answer}"
            ),
        },
    ]


def enrich_context(
    text: str, current_context: dict[str, Any], *, now: str | None = None,
) -> list[dict[str, str]]:
    """Prompt to extract context updates from user message."""
    from datetime import UTC
    from datetime import datetime as _dt

    now_str = now or _dt.now(UTC).strftime("%Y-%m-%d %H:%M UTC")
    context_str = _format_context(current_context)
    return [
        {
            "role": "system",
            "content": (
                "You are a family memory assistant. The user is sharing family context info. "
                "Extract structured updates. "
                "Respond ONLY with valid YAML (no markdown fencing).\n\n"
                f"Current date/time: {now_str}\n"
                "IMPORTANT: Resolve all relative dates (e.g. 'two weeks ago', 'last month', "
                "'yesterday') into absolute dates (YYYY-MM-DD) using the current date above.\n\n"
                "Possible updates (use a list when there are multiple items):\n"
                "  family_members:\n"
                "    - {name, role, birthday?}\n"
                "  friends:\n"
                "    - {name, relationship}\n"
                "  locations:\n"
                "    - {name, description}\n"
                "  notes:\n"
                "    - free-text fact (resolve any relative dates to absolute)\n"
                "  person_updates:\n"
                "    - {name, field, value}\n\n"
                f"Current context:\n{context_str}"
            ),
        },
        {"role": "user", "content": text},
    ]


def morning_question(
    question_text: str,
    context: dict[str, Any],
) -> list[dict[str, str]]:
    """Prompt to wrap a question in a morning greeting when there are no events for today."""
    context_str = _format_context(context)
    return [
        {
            "role": "system",
            "content": (
                "You are a warm family memory assistant sending a morning message. "
                "There are no special memories for today, so take this opportunity to learn "
                "something new about the family. Wrap the following question in a brief, "
                "friendly morning greeting (2-3 sentences total).\n\n"
                f"Question: {question_text}\n"
                f"Family context:\n{context_str}"
            ),
        },
        {"role": "user", "content": "Generate the morning greeting with the question."},
    ]


def generate_question_text(
    question_type: str,
    subject: str,
    context: dict[str, Any],
) -> list[dict[str, str]]:
    """Prompt to generate a natural-language question from a pending question record."""
    context_str = _format_context(context)
    return [
        {
            "role": "system",
            "content": (
                "You are a family memory assistant. Generate a short, friendly question to ask "
                "the user. Keep it to 1-2 sentences. Be conversational.\n\n"
                f"Question type: {question_type}\n"
                f"Subject: {subject}\n\n"
                f"Family context:\n{context_str}"
            ),
        },
        {"role": "user", "content": "Generate the question."},
    ]


def describe_image(image_base64: str, context: dict[str, Any]) -> list[dict[str, Any]]:
    """Prompt to describe an image for a family memory log using vision."""
    context_str = _format_context(context)
    return [
        {
            "role": "system",
            "content": (
                "You are a family memory assistant. Describe what's happening in the photo "
                "for a family memory log. Include who appears to be in the photo, what they're "
                "doing, and the setting. Keep it concise (2-3 sentences).\n\n"
                f"Family context:\n{context_str}"
            ),
        },
        {
            "role": "user",
            "content": [
                {"type": "text", "text": "Describe this photo for a family memory log."},
                {
                    "type": "image_url",
                    "image_url": {"url": f"data:image/jpeg;base64,{image_base64}"},
                },
            ],
        },
    ]


def conversational_system_prompt(
    context: dict[str, Any],
    people_names: list[str],
    today: str,
) -> str:
    """Build the system prompt for the conversational agent."""
    context_str = _format_context(context)
    people_str = ", ".join(people_names) if people_names else "(none registered)"
    return (
        "You are My Little Elephant, a warm and friendly family memory assistant. "
        "You help a family record, organize, and recall their memories.\n\n"
        f"Today's date: {today}\n\n"
        f"Family context:\n{context_str}\n\n"
        f"Known people: {people_str}\n\n"
        "Guidelines:\n"
        "- When the user describes something that happened, use `create_event` to save it.\n"
        "- When the user asks about memories or what happened, use `list_events` or "
        "`get_event` to search and retrieve.\n"
        "- When the user shares family information (names, birthdays, relationships), "
        "use `update_context`.\n"
        "- When the user asks about the family or context, use `get_context`.\n"
        "- For general questions or conversation, respond naturally without tools.\n"
        "- Keep responses concise and warm. Use the family's names when possible.\n"
        "- When creating events, confirm what you saved in a friendly way.\n"
        "- When listing events, summarize them naturally rather than dumping raw data.\n"
        "- When the user sends a file (photo or document), use `describe_attachment` to view/read "
        "it before responding. The file path is in the [Attachments] section.\n"
    )


def _format_context(context: dict[str, Any]) -> str:
    """Format context dict into a readable string for prompts."""
    if not context:
        return "(no context available)"
    parts: list[str] = []
    members = context.get("family", {}).get("members", [])
    if members:
        names = [f"{m.get('name', '?')} ({m.get('role', '?')})" for m in members]
        parts.append(f"Family: {', '.join(names)}")
    friends = context.get("friends", [])
    if friends:
        names = [f"{f.get('name', '?')}" for f in friends]
        parts.append(f"Friends: {', '.join(names)}")
    locations = context.get("locations", {})
    if locations:
        parts.append(f"Locations: {', '.join(locations.keys())}")
    notes = context.get("notes", [])
    if notes:
        formatted = []
        for n in notes:
            if isinstance(n, dict):
                txt = n.get("text", "")
                dt = n.get("date", "")
                formatted.append(f"[{dt}] {txt}" if dt else txt)
            else:
                formatted.append(str(n))
        parts.append(f"Notes: {'; '.join(formatted)}")
    return "\n".join(parts) if parts else "(no context available)"
