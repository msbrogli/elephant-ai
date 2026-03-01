"""Tool executor: dispatch tool calls to DataStore methods."""

from __future__ import annotations

import base64
import json
import logging
import uuid
from datetime import date
from pathlib import Path
from typing import TYPE_CHECKING, Any

from elephant.data.models import Correction, CurrentThread, MediaLinks, Memory, Person
from elephant.llm.prompts import describe_image

if TYPE_CHECKING:
    from elephant.data.store import DataStore
    from elephant.git_ops import GitRepo
    from elephant.llm.client import LLMClient, ToolCall

logger = logging.getLogger(__name__)


def _slugify(text: str) -> str:
    """Convert text to a filename-safe slug."""
    slug = text.lower().strip()
    slug = "".join(c if c.isalnum() or c == " " else "" for c in slug)
    slug = "_".join(slug.split())
    if not slug:
        slug = f"memory_{uuid.uuid4().hex[:6]}"
    return slug[:40]


_IMAGE_EXTENSIONS = {".jpg", ".jpeg", ".png", ".gif", ".webp"}
_MAX_DOCUMENT_SIZE = 100_000  # ~100 KB


class ToolExecutor:
    """Dispatches tool calls to the appropriate handlers."""

    def __init__(self, store: DataStore, git: GitRepo, llm: LLMClient, model: str) -> None:
        self._store = store
        self._git = git
        self._llm = llm
        self._model = model
        self._current_message_id: str | None = None

    def set_message_context(self, *, message_id: str | None = None) -> None:
        """Set the current message context for source tracking."""
        self._current_message_id = message_id

    async def execute(self, tool_call: ToolCall) -> str:
        """Execute a tool call and return the JSON result string."""
        try:
            args = json.loads(tool_call.arguments) if tool_call.arguments else {}
            handler = getattr(self, f"_handle_{tool_call.function_name}", None)
            if handler is None:
                return json.dumps({"error": f"Unknown tool: {tool_call.function_name}"})
            result = await handler(args)
            return json.dumps(result, default=str)
        except Exception as e:
            logger.warning("Tool execution failed: %s", e, exc_info=True)
            return json.dumps({"error": str(e)})

    async def _handle_list_memories(self, args: dict[str, Any]) -> Any:
        date_from = _parse_date(args.get("date_from"))
        date_to = _parse_date(args.get("date_to"))
        memories = self._store.list_memories(
            date_from=date_from,
            date_to=date_to,
            people=args.get("people"),
            memory_type=args.get("memory_type"),
            tags=args.get("tags"),
            query=args.get("query"),
            limit=args.get("limit", 20),
        )
        return {
            "count": len(memories),
            "memories": [_memory_summary(m) for m in memories],
        }

    async def _handle_get_memory(self, args: dict[str, Any]) -> Any:
        memory = self._store.find_memory_by_id(args["memory_id"])
        if memory is None:
            return {"error": f"Memory not found: {args['memory_id']}"}
        return memory.model_dump(mode="json", exclude_none=True)

    async def _handle_create_memory(self, args: dict[str, Any]) -> Any:
        memory_date = _parse_date(args["date"]) or date.today()
        slug = _slugify(args["title"])
        memory_id = f"{memory_date.strftime('%Y%m%d')}_{slug}"

        media = None
        media_data = args.get("media")
        if media_data and isinstance(media_data, dict):
            media = MediaLinks(
                photos=media_data.get("photos", []),
                videos=media_data.get("videos", []),
            )

        # Check confidence threshold
        confidence = float(args.get("confidence", 1.0))
        if confidence < 0.6:
            return {
                "needs_clarification": True,
                "confidence": confidence,
                "title": args.get("title", ""),
                "message": (
                    "I'm not very confident about this memory. "
                    "Could you clarify what happened?"
                ),
            }

        source_message_ids: list[str] = []
        if self._current_message_id:
            source_message_ids = [self._current_message_id]

        memory = Memory(
            id=memory_id,
            date=memory_date,
            time=args.get("time"),
            title=args["title"],
            type=args.get("type", "other"),
            description=args["description"],
            people=args.get("people", []),
            location=args.get("location"),
            media=media,
            source=args.get("source", "agent"),
            source_message_ids=source_message_ids,
            nostalgia_score=float(args.get("nostalgia_score", 1.0)),
            tags=args.get("tags", []),
            content=args.get("content"),
            participants=args.get("participants", []),
        )

        # Check for unknown people before writing
        auto_create = args.get("auto_create_people", False)
        if not auto_create and memory.people:
            _, unmatched = self._find_unmatched_people(memory.people)
            if unmatched:
                suggestions: dict[str, list[str]] = {}
                for name in unmatched:
                    near = self._find_near_matches(name)
                    if near:
                        suggestions[name] = near
                return {
                    "warning": "unknown_people",
                    "unknown_names": unmatched,
                    "suggestions": suggestions,
                    "message": (
                        f"I don't recognize: {', '.join(unmatched)}. "
                        "Are these new people, or did you mean someone else? "
                        "If new, ask the user for their full name (first + surname) "
                        "before creating them."
                    ),
                }

        path = self._store.write_memory(memory)
        self._git.auto_commit("memory", memory.title, timestamp=memory.date, paths=[path])

        # Auto-create confirmed unknowns
        if auto_create:
            self._auto_create_people(memory.people, memory.date)

        logger.info("Agent created memory: %s", memory_id)
        return {"created": memory_id, "title": memory.title, "date": str(memory.date)}

    async def _handle_update_memory(self, args: dict[str, Any]) -> Any:
        from datetime import UTC
        from datetime import datetime as _datetime

        memory_id = args.pop("memory_id")
        reason = args.pop("reason", None)
        allowed = {"title", "description", "people", "location", "tags", "time", "type",
                    "nostalgia_score", "content", "participants"}
        updates = {k: v for k, v in args.items() if k in allowed}

        memory = self._store.find_memory_by_id(memory_id)
        if memory is None:
            return {"error": f"Memory not found: {memory_id}"}

        if memory.date < date.today():
            # Past memory: append corrections instead of overwriting
            corrections = list(memory.corrections)
            for field, new_val in updates.items():
                old_val = getattr(memory, field, None)
                corrections.append(Correction(
                    timestamp=_datetime.now(UTC),
                    field=field,
                    old_value=str(old_val) if old_val is not None else None,
                    new_value=str(new_val) if new_val is not None else None,
                    reason=reason,
                ))
            updated = memory.model_copy(update={"corrections": corrections})
            path = self._store.write_memory(updated)
            self._git.auto_commit(
                "memory", f"Corrected {memory.title}", timestamp=memory.date, paths=[path],
            )
            return {"corrected": memory_id, "title": memory.title,
                    "fields": list(updates.keys())}
        else:
            # Same-day: direct update
            updated = memory.model_copy(update=updates)
            path = self._store.write_memory(updated)
            self._git.auto_commit(
                "memory", f"Updated {memory.title}", timestamp=memory.date, paths=[path],
            )
            return {"updated": memory_id, "title": memory.title}

    async def _handle_delete_memory(self, args: dict[str, Any]) -> Any:
        memory_id = args["memory_id"]
        deleted = self._store.delete_memory(memory_id)
        if not deleted:
            return {"error": f"Memory not found: {memory_id}"}
        self._git.auto_commit("memory", f"Deleted {memory_id}")
        return {"deleted": memory_id}

    async def _handle_search_people(self, args: dict[str, Any]) -> Any:
        name_query = args.get("name", "").lower()
        all_people = self._store.read_all_people()
        matches = [
            p for p in all_people
            if name_query in p.display_name.lower() or name_query in p.person_id.lower()
        ]
        last_contacts = self._store.get_latest_memory_dates_for_people(
            [p.display_name for p in matches],
        )
        return {
            "count": len(matches),
            "people": [
                {
                    "person_id": p.person_id,
                    "display_name": p.display_name,
                    "relationship": p.relationship,
                    "last_contact": (
                        str(last_contacts.get(p.display_name))
                        if last_contacts.get(p.display_name) else None
                    ),
                    "current_threads": [
                        {
                            "topic": t.topic,
                            "latest_update": t.latest_update,
                            "last_mentioned_date": str(t.last_mentioned_date),
                        }
                        for t in p.current_threads
                    ],
                }
                for p in matches
            ],
        }

    async def _handle_get_person(self, args: dict[str, Any]) -> Any:
        person_id = args.get("person_id", "")
        person = self._store.read_person(person_id)
        if person is None:
            return {"error": f"Person not found: {person_id}"}
        data = person.model_dump(mode="json", exclude_none=True)
        last_contact = self._store.get_latest_memory_date_for_person(person.display_name)
        if last_contact:
            data["last_contact"] = str(last_contact)
        return data

    async def _handle_list_people(self, args: dict[str, Any]) -> Any:
        people = self._store.read_all_people()
        last_contacts = self._store.get_latest_memory_dates_for_people(
            [p.display_name for p in people],
        )
        return {
            "people": [
                {
                    "person_id": p.person_id,
                    "display_name": p.display_name,
                    "relationship": p.relationship,
                    "birthday": str(p.birthday) if p.birthday else None,
                    "close_friend": p.close_friend,
                    "last_contact": (
                        str(last_contacts.get(p.display_name))
                        if last_contacts.get(p.display_name) else None
                    ),
                    "current_threads": [
                        {"topic": t.topic, "latest_update": t.latest_update}
                        for t in p.current_threads
                    ],
                }
                for p in people
            ]
        }

    async def _handle_update_person(self, args: dict[str, Any]) -> Any:
        from elephant.brain.clarification import detect_person_conflicts

        person_id = args.get("person_id", "")
        force = args.pop("force", False)
        person = self._store.read_person(person_id)
        if person is None:
            return {"error": f"Person not found: {person_id}"}
        allowed = {
            "display_name", "relationship", "birthday", "close_friend",
            "notes", "interaction_frequency_target",
        }
        updates: dict[str, Any] = {k: v for k, v in args.items() if k in allowed}
        if "birthday" in updates and isinstance(updates["birthday"], str):
            updates["birthday"] = _parse_date(updates["birthday"])

        # Check for conflicts on canonical fields
        if not force:
            conflicts = detect_person_conflicts(person, updates)
            if conflicts:
                return {
                    "conflict": True,
                    "conflicts": conflicts,
                    "message": (
                        "These fields already have values that differ from the new ones. "
                        "Ask the user which value is correct, then re-call with force: true."
                    ),
                }

        # Handle current_threads
        if "current_threads" in args:
            threads_data = args["current_threads"]
            threads = []
            for t in threads_data:
                if isinstance(t, dict):
                    threads.append(CurrentThread(
                        topic=t["topic"],
                        latest_update=t["latest_update"],
                        last_mentioned_date=_parse_date(t["last_mentioned_date"]) or date.today(),
                    ))
            updates["current_threads"] = threads

        updated = person.model_copy(update=updates)

        # Handle archive_threads: move matching threads to archived_threads
        archive_topics = args.get("archive_threads")
        if archive_topics:
            archive_set = {t.lower() for t in archive_topics}
            remaining: list[CurrentThread] = []
            newly_archived: list[CurrentThread] = list(updated.archived_threads)
            for thread in updated.current_threads:
                if thread.topic.lower() in archive_set:
                    newly_archived.append(thread)
                else:
                    remaining.append(thread)
            updated = updated.model_copy(update={
                "current_threads": remaining,
                "archived_threads": newly_archived,
            })

        path = self._store.write_person(updated)
        self._git.auto_commit(
            "people", f"Updated {updated.display_name}", paths=[path],
        )
        return {"updated": person_id, "display_name": updated.display_name}

    async def _handle_update_locations(self, args: dict[str, Any]) -> Any:
        locations = args.get("locations", {})
        if not locations:
            return {"updated": False}
        prefs = self._store.read_preferences()
        prefs.locations.update(locations)
        self._store.write_preferences(prefs)
        self._git.auto_commit("preferences", "Updated locations")
        return {"updated": True, "locations": prefs.locations}

    async def _handle_add_note(self, args: dict[str, Any]) -> Any:
        note = args.get("note", "")
        if not note:
            return {"updated": False}
        prefs = self._store.read_preferences()
        prefs.notes.append(note)
        self._store.write_preferences(prefs)
        self._git.auto_commit("preferences", "Added note")
        return {"updated": True, "note": note}

    def _find_unmatched_people(self, people_names: list[str]) -> tuple[list[str], list[str]]:
        """Split names into matched (existing) and unmatched (unknown)."""
        all_people = self._store.read_all_people()
        existing: set[str] = {p.display_name.lower() for p in all_people}
        matched: list[str] = []
        unmatched: list[str] = []
        for name in people_names:
            if name.lower() in existing:
                matched.append(name)
            else:
                unmatched.append(name)
        return matched, unmatched

    def _find_near_matches(self, name: str) -> list[str]:
        """Find existing people whose names are similar to the given name."""
        all_people = self._store.read_all_people()
        name_lower = name.lower()
        suggestions: list[str] = []
        for p in all_people:
            existing = p.display_name.lower()
            if name_lower in existing or existing in name_lower:
                suggestions.append(p.display_name)
        return suggestions

    def _auto_create_people(self, people_names: list[str], memory_date: date) -> None:
        """Auto-create Person files for the given names."""
        all_people = self._store.read_all_people()
        existing: set[str] = {p.display_name.lower() for p in all_people}
        for name in people_names:
            if name.lower() not in existing:
                new_person = Person(
                    person_id=_slugify(name),
                    display_name=name,
                    relationship="unknown",
                )
                path = self._store.write_person(new_person)
                self._git.auto_commit(
                    "people", f"Auto-created {name}", paths=[path],
                )
                existing.add(name.lower())

    async def _handle_describe_attachment(self, args: dict[str, Any]) -> Any:
        file_path = args.get("file_path", "")
        path = Path(file_path)

        if not path.is_file():
            return {"error": f"File not found: {file_path}"}

        suffix = path.suffix.lower()

        if suffix in _IMAGE_EXTENSIONS:
            # Vision API for images
            image_bytes = path.read_bytes()
            image_b64 = base64.b64encode(image_bytes).decode()
            people = self._store.read_all_people()
            prefs = self._store.read_preferences()
            messages = describe_image(image_b64, people, prefs)
            response = await self._llm.chat(messages, model=self._model, temperature=0.5)
            return {"description": response.content or "Could not describe image."}

        # Text-based document
        try:
            content = path.read_text(encoding="utf-8")
        except (UnicodeDecodeError, OSError) as e:
            return {"error": f"Could not read file: {e}"}

        if len(content) > _MAX_DOCUMENT_SIZE:
            content = content[:_MAX_DOCUMENT_SIZE]

        return {"file_type": suffix.lstrip(".") or "txt", "contents": content}


def _parse_date(value: str | None) -> date | None:
    if not value:
        return None
    try:
        return date.fromisoformat(value)
    except ValueError:
        return None


def _memory_summary(memory: Memory) -> dict[str, Any]:
    return {
        "id": memory.id,
        "date": str(memory.date),
        "title": memory.title,
        "type": memory.type,
        "description": memory.description,
        "people": memory.people,
        "location": memory.location,
    }
