"""DataStore: directory init, YAML read/write, schema deployment."""

from __future__ import annotations

import os
from datetime import date
from typing import Any

import yaml

from elephant.atomic import atomic_write
from elephant.data.models import (
    AuthorizedChat,
    AuthorizedChatsFile,
    DigestState,
    Event,
    PendingQuestionsFile,
    Person,
    PhotoEntry,
    PreferencesFile,
    VideoEntry,
)
from elephant.data.schemas import DIR_SCHEMAS, SINGLE_FILE_SCHEMAS

# Directories to create under data_dir
_DIRS = [
    "events",
    "photo_index",
    "video_index",
    "people",
    "faces",
    "logs",
    "media",
]


class DataStore:
    """Centralized YAML I/O with path helpers and schema deployment."""

    def __init__(self, data_dir: str) -> None:
        self.data_dir = os.path.abspath(data_dir)

    def initialize(self) -> None:
        """Create directory structure and deploy schemas. Idempotent."""
        for d in _DIRS:
            os.makedirs(os.path.join(self.data_dir, d), exist_ok=True)

        # Deploy directory schemas (e.g. events/_schema.yaml)
        for rel_path, content in DIR_SCHEMAS.items():
            full_path = os.path.join(self.data_dir, rel_path)
            os.makedirs(os.path.dirname(full_path), exist_ok=True)
            atomic_write(full_path, content)

        # Deploy single-file schemas (only if file doesn't exist yet)
        for rel_path, content in SINGLE_FILE_SCHEMAS.items():
            full_path = os.path.join(self.data_dir, rel_path)
            if not os.path.exists(full_path):
                atomic_write(full_path, content)

        # Deploy .gitignore for the data repo
        gitignore_path = os.path.join(self.data_dir, ".gitignore")
        if not os.path.exists(gitignore_path):
            atomic_write(
                gitignore_path,
                "faces/\nlogs/\n*.jpg\n*.jpeg\n*.png\n*.mp4\n*.mov\n",
            )

        # Migrate legacy people.yaml to people/ directory
        self._migrate_people_file()

        # Migrate legacy authorized_chat_id
        ac = self.read_authorized_chats()
        if not ac.chats:
            state = self.read_digest_state()
            if state.authorized_chat_id:
                ac.chats.append(
                    AuthorizedChat(chat_id=state.authorized_chat_id, status="approved")
                )
                self.write_authorized_chats(ac)

    def _migrate_people_file(self) -> None:
        """Migrate legacy people.yaml to people/ directory. Idempotent."""
        old_path = os.path.join(self.data_dir, "people.yaml")
        if not os.path.exists(old_path):
            return
        raw = self._read_yaml(old_path)
        if not isinstance(raw, dict):
            os.remove(old_path)
            return
        people_list = raw.get("people", [])
        if not people_list:
            os.remove(old_path)
            return
        for person_data in people_list:
            if isinstance(person_data, dict) and "person_id" in person_data:
                person = Person.model_validate(person_data)
                self.write_person(person)
        os.remove(old_path)

    def media_dir(self) -> str:
        """Return the path to the media directory."""
        return os.path.join(self.data_dir, "media")

    # --- Path helpers ---

    def _event_path(self, event_date: date, slug: str) -> str:
        return os.path.join(
            self.data_dir,
            "events",
            event_date.strftime("%Y"),
            event_date.strftime("%m"),
            f"{event_date.strftime('%Y%m%d')}_{slug}.yaml",
        )

    def _photo_index_path(self, index_date: date) -> str:
        return os.path.join(
            self.data_dir,
            "photo_index",
            index_date.strftime("%Y"),
            index_date.strftime("%m"),
            f"{index_date.isoformat()}.yaml",
        )

    def _video_index_path(self, index_date: date) -> str:
        return os.path.join(
            self.data_dir,
            "video_index",
            index_date.strftime("%Y"),
            index_date.strftime("%m"),
            f"{index_date.isoformat()}.yaml",
        )

    def _single_file_path(self, name: str) -> str:
        return os.path.join(self.data_dir, name)

    # --- YAML I/O helpers ---

    @staticmethod
    def _read_yaml(path: str) -> Any:
        with open(path) as f:
            return yaml.safe_load(f)

    @staticmethod
    def _write_yaml(path: str, data: Any) -> None:
        content = yaml.dump(data, default_flow_style=False, allow_unicode=True, sort_keys=False)
        atomic_write(path, content)

    # --- Events ---

    def write_event(self, event: Event) -> str:
        """Write an event to its date-based path. Returns the file path."""
        slug = event.id.split("_", 1)[1] if "_" in event.id else event.id
        path = self._event_path(event.date, slug)
        self._write_yaml(path, event.model_dump(mode="json", exclude_none=True))
        return path

    def read_event(self, path: str) -> Event:
        """Read an event from a YAML file."""
        data = self._read_yaml(path)
        return Event.model_validate(data)

    # --- Photo Index ---

    def write_photo_index(self, index_date: date, entries: list[PhotoEntry]) -> str:
        """Write photo index entries for a date. Returns the file path."""
        path = self._photo_index_path(index_date)
        data = [e.model_dump(mode="json", exclude_none=True) for e in entries]
        self._write_yaml(path, data)
        return path

    def read_photo_index(self, index_date: date) -> list[PhotoEntry]:
        """Read photo index entries for a date."""
        path = self._photo_index_path(index_date)
        if not os.path.exists(path):
            return []
        data = self._read_yaml(path)
        if not data:
            return []
        return [PhotoEntry.model_validate(item) for item in data]

    # --- Video Index ---

    def write_video_index(self, index_date: date, entries: list[VideoEntry]) -> str:
        """Write video index entries for a date. Returns the file path."""
        path = self._video_index_path(index_date)
        data = [e.model_dump(mode="json", exclude_none=True) for e in entries]
        self._write_yaml(path, data)
        return path

    def read_video_index(self, index_date: date) -> list[VideoEntry]:
        """Read video index entries for a date."""
        path = self._video_index_path(index_date)
        if not os.path.exists(path):
            return []
        data = self._read_yaml(path)
        if not data:
            return []
        return [VideoEntry.model_validate(item) for item in data]

    # --- Single-file stores (preserve _schema block) ---

    def _read_single_file(self, name: str) -> dict[str, Any]:
        path = self._single_file_path(name)
        if not os.path.exists(path):
            return {}
        data = self._read_yaml(path)
        return data if isinstance(data, dict) else {}

    def _write_single_file(self, name: str, data: dict[str, Any]) -> None:
        """Write a single-file store, preserving the _schema block."""
        path = self._single_file_path(name)
        existing = self._read_single_file(name)
        schema = existing.get("_schema")
        if schema is not None:
            data = {"_schema": schema, **{k: v for k, v in data.items() if k != "_schema"}}
        self._write_yaml(path, data)

    # --- People (directory-based) ---

    def _person_path(self, person_id: str) -> str:
        return os.path.join(self.data_dir, "people", f"{person_id}.yaml")

    def read_person(self, person_id: str) -> Person | None:
        """Read a single person by ID. Returns None if not found."""
        path = self._person_path(person_id)
        if not os.path.exists(path):
            return None
        data = self._read_yaml(path)
        if not data:
            return None
        return Person.model_validate(data)

    def write_person(self, person: Person) -> str:
        """Write a person to their file. Returns the file path."""
        path = self._person_path(person.person_id)
        self._write_yaml(path, person.model_dump(mode="json", exclude_none=True))
        return path

    def read_all_people(self) -> list[Person]:
        """Read all people from the people directory."""
        people_dir = os.path.join(self.data_dir, "people")
        if not os.path.isdir(people_dir):
            return []
        results: list[Person] = []
        for fname in sorted(os.listdir(people_dir)):
            if not fname.endswith(".yaml") or fname.startswith("_"):
                continue
            path = os.path.join(people_dir, fname)
            try:
                data = self._read_yaml(path)
                if data:
                    results.append(Person.model_validate(data))
            except Exception:
                continue
        return results

    def delete_person(self, person_id: str) -> bool:
        """Delete a person by ID. Returns True if deleted."""
        path = self._person_path(person_id)
        if not os.path.exists(path):
            return False
        os.remove(path)
        return True

    # --- Preferences ---

    def read_preferences(self) -> PreferencesFile:
        raw = self._read_single_file("preferences.yaml")
        return PreferencesFile.model_validate(
            {
                "nostalgia_weights": raw.get("nostalgia_weights", {}),
                "tone_preference": raw.get("tone_preference", {}),
            }
        )

    def write_preferences(self, prefs: PreferencesFile) -> None:
        self._write_single_file(
            "preferences.yaml",
            prefs.model_dump(mode="json"),
        )

    # --- Pending Questions ---

    def read_pending_questions(self) -> PendingQuestionsFile:
        raw = self._read_single_file("pending_questions.yaml")
        return PendingQuestionsFile.model_validate({"questions": raw.get("questions", [])})

    def write_pending_questions(self, pq: PendingQuestionsFile) -> None:
        self._write_single_file(
            "pending_questions.yaml",
            pq.model_dump(mode="json", exclude_none=True),
        )

    # --- Context (free-form dict) ---

    def read_context(self) -> dict[str, Any]:
        raw = self._read_single_file("context.yaml")
        return {k: v for k, v in raw.items() if k != "_schema"}

    def write_context(self, context: dict[str, Any]) -> None:
        self._write_single_file("context.yaml", context)

    # --- Digest State ---

    def read_digest_state(self) -> DigestState:
        raw = self._read_single_file("digest_state.yaml")
        return DigestState.model_validate(
            {
                "last_digest_sent_at": raw.get("last_digest_sent_at"),
                "last_digest_event_ids": raw.get("last_digest_event_ids", []),
                "last_digest_message_id": raw.get("last_digest_message_id"),
                "authorized_chat_id": raw.get("authorized_chat_id"),
            }
        )

    def write_digest_state(self, state: DigestState) -> None:
        self._write_single_file(
            "digest_state.yaml",
            state.model_dump(mode="json", exclude_none=True),
        )

    # --- Authorized Chats ---

    def read_authorized_chats(self) -> AuthorizedChatsFile:
        raw = self._read_single_file("authorized_chats.yaml")
        return AuthorizedChatsFile.model_validate({"chats": raw.get("chats", [])})

    def write_authorized_chats(self, ac: AuthorizedChatsFile) -> None:
        self._write_single_file(
            "authorized_chats.yaml",
            ac.model_dump(mode="json", exclude_none=True),
        )

    # --- Event querying ---

    def query_events_by_month_day(self, month: int, day: int) -> list[Event]:
        """Find events matching a given month and day across all years."""
        events_dir = os.path.join(self.data_dir, "events")
        if not os.path.isdir(events_dir):
            return []

        month_str = f"{month:02d}"
        day_str = f"{day:02d}"
        results: list[Event] = []

        for year_name in sorted(os.listdir(events_dir)):
            year_dir = os.path.join(events_dir, year_name)
            if not os.path.isdir(year_dir) or year_name.startswith("_"):
                continue
            month_dir = os.path.join(year_dir, month_str)
            if not os.path.isdir(month_dir):
                continue
            for fname in sorted(os.listdir(month_dir)):
                if not fname.endswith(".yaml") or fname.startswith("_"):
                    continue
                # Filename format: YYYYMMDD_slug.yaml — check day digits [6:8]
                if len(fname) >= 8 and fname[6:8] == day_str:
                    path = os.path.join(month_dir, fname)
                    results.append(self.read_event(path))

        return results

    # --- Event CRUD ---

    def list_events(
        self,
        date_from: date | None = None,
        date_to: date | None = None,
        people: list[str] | None = None,
        event_type: str | None = None,
        tags: list[str] | None = None,
        query: str | None = None,
        limit: int = 20,
    ) -> list[Event]:
        """List events with optional filters. Returns newest first."""
        events_dir = os.path.join(self.data_dir, "events")
        if not os.path.isdir(events_dir):
            return []

        results: list[Event] = []

        for year_name in sorted(os.listdir(events_dir)):
            year_dir = os.path.join(events_dir, year_name)
            if not os.path.isdir(year_dir) or year_name.startswith("_"):
                continue
            # Skip irrelevant years
            try:
                year_int = int(year_name)
            except ValueError:
                continue
            if date_from and year_int < date_from.year:
                continue
            if date_to and year_int > date_to.year:
                continue

            for month_name in sorted(os.listdir(year_dir)):
                month_dir = os.path.join(year_dir, month_name)
                if not os.path.isdir(month_dir) or month_name.startswith("_"):
                    continue

                for fname in sorted(os.listdir(month_dir)):
                    if not fname.endswith(".yaml") or fname.startswith("_"):
                        continue
                    path = os.path.join(month_dir, fname)
                    try:
                        event = self.read_event(path)
                    except Exception:
                        continue

                    # Apply filters
                    if date_from and event.date < date_from:
                        continue
                    if date_to and event.date > date_to:
                        continue
                    if event_type and event.type != event_type:
                        continue
                    if people:
                        lower_people = [p.lower() for p in people]
                        if not any(p.lower() in lower_people for p in event.people):
                            continue
                    if tags:
                        lower_tags = [t.lower() for t in tags]
                        if not any(t.lower() in lower_tags for t in event.tags):
                            continue
                    if query:
                        q = query.lower()
                        if (
                            q not in event.title.lower()
                            and q not in event.description.lower()
                        ):
                            continue

                    results.append(event)

        # Sort newest first, apply limit
        results.sort(key=lambda e: e.date, reverse=True)
        return results[:limit]

    def find_event_by_id(self, event_id: str) -> Event | None:
        """Find an event by its ID. Returns None if not found."""
        # Parse date from ID (first 8 chars: YYYYMMDD)
        if len(event_id) < 9 or event_id[8] != "_":
            return None
        date_str = event_id[:8]
        slug = event_id[9:]
        try:
            event_date = date(int(date_str[:4]), int(date_str[4:6]), int(date_str[6:8]))
        except ValueError:
            return None

        path = self._event_path(event_date, slug)
        if not os.path.exists(path):
            return None
        return self.read_event(path)

    def update_event(self, event_id: str, updates: dict[str, Any]) -> Event | None:
        """Update fields on an existing event. Returns updated event or None."""
        event = self.find_event_by_id(event_id)
        if event is None:
            return None
        updated = event.model_copy(update=updates)
        self.write_event(updated)
        return updated

    def delete_event(self, event_id: str) -> bool:
        """Delete an event by ID. Returns True if deleted."""
        if len(event_id) < 9 or event_id[8] != "_":
            return False
        date_str = event_id[:8]
        slug = event_id[9:]
        try:
            event_date = date(int(date_str[:4]), int(date_str[4:6]), int(date_str[6:8]))
        except ValueError:
            return False

        path = self._event_path(event_date, slug)
        if not os.path.exists(path):
            return False
        os.remove(path)
        return True
