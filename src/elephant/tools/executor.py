"""Tool executor: dispatch tool calls to DataStore methods."""

from __future__ import annotations

import base64
import json
import logging
import uuid
from datetime import date
from pathlib import Path
from typing import TYPE_CHECKING, Any

from elephant.data.models import Event, MediaLinks
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
        slug = f"event_{uuid.uuid4().hex[:6]}"
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

    async def _handle_list_events(self, args: dict[str, Any]) -> Any:
        date_from = _parse_date(args.get("date_from"))
        date_to = _parse_date(args.get("date_to"))
        events = self._store.list_events(
            date_from=date_from,
            date_to=date_to,
            people=args.get("people"),
            event_type=args.get("event_type"),
            tags=args.get("tags"),
            query=args.get("query"),
            limit=args.get("limit", 20),
        )
        return {
            "count": len(events),
            "events": [_event_summary(e) for e in events],
        }

    async def _handle_get_event(self, args: dict[str, Any]) -> Any:
        event = self._store.find_event_by_id(args["event_id"])
        if event is None:
            return {"error": f"Event not found: {args['event_id']}"}
        return event.model_dump(mode="json", exclude_none=True)

    async def _handle_create_event(self, args: dict[str, Any]) -> Any:
        event_date = _parse_date(args["date"]) or date.today()
        slug = _slugify(args["title"])
        event_id = f"{event_date.strftime('%Y%m%d')}_{slug}"

        media = None
        media_data = args.get("media")
        if media_data and isinstance(media_data, dict):
            media = MediaLinks(
                photos=media_data.get("photos", []),
                videos=media_data.get("videos", []),
            )

        event = Event(
            id=event_id,
            date=event_date,
            time=args.get("time"),
            title=args["title"],
            type=args.get("type", "other"),
            description=args["description"],
            people=args.get("people", []),
            location=args.get("location"),
            media=media,
            source=args.get("source", "agent"),
            nostalgia_score=float(args.get("nostalgia_score", 1.0)),
            tags=args.get("tags", []),
        )

        path = self._store.write_event(event)
        self._git.auto_commit("event", event.title, timestamp=event.date, paths=[path])

        # Auto-update last_contact for mentioned people
        self._update_last_contact(event.people, event.date)

        logger.info("Agent created event: %s", event_id)
        return {"created": event_id, "title": event.title, "date": str(event.date)}

    async def _handle_update_event(self, args: dict[str, Any]) -> Any:
        event_id = args.pop("event_id")
        # Only pass valid update fields
        allowed = {"title", "description", "people", "location", "tags", "time", "type",
                    "nostalgia_score"}
        updates = {k: v for k, v in args.items() if k in allowed}
        event = self._store.update_event(event_id, updates)
        if event is None:
            return {"error": f"Event not found: {event_id}"}
        path = self._store.write_event(event)
        self._git.auto_commit("event", f"Updated {event.title}", timestamp=event.date, paths=[path])
        return {"updated": event_id, "title": event.title}

    async def _handle_delete_event(self, args: dict[str, Any]) -> Any:
        event_id = args["event_id"]
        deleted = self._store.delete_event(event_id)
        if not deleted:
            return {"error": f"Event not found: {event_id}"}
        self._git.auto_commit("event", f"Deleted {event_id}")
        return {"deleted": event_id}

    async def _handle_get_context(self, args: dict[str, Any]) -> Any:
        return self._store.read_context()

    async def _handle_update_context(self, args: dict[str, Any]) -> Any:
        context = self._store.read_context()
        changed = False

        for member in args.get("family_members", []):
            if isinstance(member, dict) and "name" in member:
                family = context.setdefault("family", {})
                members = family.setdefault("members", [])
                # Update existing or append
                found = False
                for existing in members:
                    if existing.get("name") == member["name"]:
                        existing.update(member)
                        found = True
                        break
                if not found:
                    members.append(member)
                changed = True

        for friend in args.get("friends", []):
            if isinstance(friend, dict) and "name" in friend:
                friends = context.setdefault("friends", [])
                found = False
                for existing in friends:
                    if existing.get("name") == friend["name"]:
                        existing.update(friend)
                        found = True
                        break
                if not found:
                    friends.append(friend)
                changed = True

        for loc in args.get("locations", []):
            if isinstance(loc, dict) and "name" in loc:
                locations = context.setdefault("locations", {})
                locations[loc["name"]] = loc.get("description", "")
                changed = True

        today = date.today().isoformat()
        for note in args.get("notes", []):
            if note:
                notes = context.setdefault("notes", [])
                notes.append({"text": str(note), "date": today})
                changed = True

        if changed:
            self._store.write_context(context)
            self._git.auto_commit("context", "Context update from agent")

        return {"updated": changed}

    async def _handle_list_people(self, args: dict[str, Any]) -> Any:
        people = self._store.read_all_people()
        return {
            "people": [
                {
                    "person_id": p.person_id,
                    "display_name": p.display_name,
                    "relationship": p.relationship,
                    "birthday": str(p.birthday) if p.birthday else None,
                    "close_friend": p.close_friend,
                    "last_contact": str(p.last_contact) if p.last_contact else None,
                }
                for p in people
            ]
        }

    async def _handle_update_person(self, args: dict[str, Any]) -> Any:
        person_id = args.get("person_id", "")
        person = self._store.read_person(person_id)
        if person is None:
            return {"error": f"Person not found: {person_id}"}
        allowed = {
            "display_name", "relationship", "birthday", "close_friend",
            "last_contact", "notes",
        }
        updates = {k: v for k, v in args.items() if k in allowed}
        if "birthday" in updates and isinstance(updates["birthday"], str):
            updates["birthday"] = _parse_date(updates["birthday"])
        if "last_contact" in updates and isinstance(updates["last_contact"], str):
            updates["last_contact"] = _parse_date(updates["last_contact"])
        updated = person.model_copy(update=updates)
        path = self._store.write_person(updated)
        self._git.auto_commit(
            "people", f"Updated {updated.display_name}", paths=[path],
        )
        return {"updated": person_id, "display_name": updated.display_name}

    def _update_last_contact(self, people_names: list[str], event_date: date) -> None:
        """Update last_contact for people mentioned in an event."""
        if not people_names:
            return
        all_people = self._store.read_all_people()
        lower_names = {n.lower() for n in people_names}
        for person in all_people:
            if (
                person.display_name.lower() in lower_names
                and (person.last_contact is None or event_date > person.last_contact)
            ):
                updated = person.model_copy(update={"last_contact": event_date})
                self._store.write_person(updated)

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
            context = self._store.read_context()
            messages = describe_image(image_b64, context)
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


def _event_summary(event: Event) -> dict[str, Any]:
    return {
        "id": event.id,
        "date": str(event.date),
        "title": event.title,
        "type": event.type,
        "description": event.description,
        "people": event.people,
        "location": event.location,
    }
