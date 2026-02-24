"""Tests for DataStore."""

import os
from datetime import date, datetime

import yaml

from elephant.data.models import (
    AuthorizedChat,
    AuthorizedChatsFile,
    DigestState,
    Event,
    PendingQuestion,
    PendingQuestionsFile,
    Person,
    PhotoEntry,
    PreferencesFile,
    VideoEntry,
)
from elephant.data.store import DataStore


class TestInitialize:
    def test_creates_directories(self, data_dir):
        store = DataStore(data_dir)
        store.initialize()
        assert os.path.isdir(os.path.join(data_dir, "events"))
        assert os.path.isdir(os.path.join(data_dir, "photo_index"))
        assert os.path.isdir(os.path.join(data_dir, "video_index"))
        assert os.path.isdir(os.path.join(data_dir, "people"))
        assert os.path.isdir(os.path.join(data_dir, "faces"))
        assert os.path.isdir(os.path.join(data_dir, "logs"))

    def test_deploys_dir_schemas(self, data_dir):
        store = DataStore(data_dir)
        store.initialize()
        for schema_path in [
            os.path.join(data_dir, "events", "_schema.yaml"),
            os.path.join(data_dir, "people", "_schema.yaml"),
        ]:
            assert os.path.exists(schema_path)
            with open(schema_path) as f:
                data = yaml.safe_load(f)
            assert data["version"] == 1

    def test_deploys_single_file_schemas(self, data_dir):
        store = DataStore(data_dir)
        store.initialize()
        for name in ["context.yaml", "preferences.yaml", "pending_questions.yaml"]:
            path = os.path.join(data_dir, name)
            assert os.path.exists(path), f"{name} not found"
            with open(path) as f:
                data = yaml.safe_load(f)
            assert "_schema" in data

    def test_idempotent(self, data_dir):
        store = DataStore(data_dir)
        store.initialize()
        store.initialize()  # should not error

    def test_does_not_overwrite_people_dir(self, data_dir):
        store = DataStore(data_dir)
        store.initialize()

        # Write a person
        store.write_person(
            Person(person_id="test", display_name="Test", relationship="friend")
        )

        # Re-initialize should not overwrite
        store.initialize()
        people = store.read_all_people()
        assert len(people) == 1

    def test_creates_gitignore(self, data_dir):
        store = DataStore(data_dir)
        store.initialize()
        assert os.path.exists(os.path.join(data_dir, ".gitignore"))


class TestEvents:
    def test_write_and_read_event(self, data_dir):
        store = DataStore(data_dir)
        store.initialize()
        event = Event(
            id="20260224_first_steps",
            date=date(2026, 2, 24),
            time="14:15",
            title="Lily's first steps",
            type="milestone",
            description="Lily took 4 steps!",
            people=["Lily", "Dad"],
            source="WhatsApp",
        )
        path = store.write_event(event)
        assert os.path.exists(path)
        assert "2026/02/20260224_first_steps.yaml" in path

        loaded = store.read_event(path)
        assert loaded.id == event.id
        assert loaded.title == event.title
        assert loaded.people == event.people


class TestPhotoIndex:
    def test_write_and_read(self, data_dir):
        store = DataStore(data_dir)
        store.initialize()
        d = date(2026, 2, 24)
        entries = [
            PhotoEntry(
                photo_id="2026/02/IMG_4455.JPG",
                sha256="abc123",
                taken_at=datetime(2026, 2, 24, 14, 14, 55),
                source="google_photos",
            ),
        ]
        path = store.write_photo_index(d, entries)
        assert os.path.exists(path)

        loaded = store.read_photo_index(d)
        assert len(loaded) == 1
        assert loaded[0].photo_id == "2026/02/IMG_4455.JPG"

    def test_read_nonexistent(self, data_dir):
        store = DataStore(data_dir)
        store.initialize()
        assert store.read_photo_index(date(2020, 1, 1)) == []


class TestVideoIndex:
    def test_write_and_read(self, data_dir):
        store = DataStore(data_dir)
        store.initialize()
        d = date(2026, 2, 24)
        entries = [
            VideoEntry(
                video_id="2026/02/VID_0012.MP4",
                sha256="def456",
                taken_at=datetime(2026, 2, 24, 14, 15, 0),
                source="google_photos",
            ),
        ]
        path = store.write_video_index(d, entries)
        assert os.path.exists(path)

        loaded = store.read_video_index(d)
        assert len(loaded) == 1
        assert loaded[0].video_id == "2026/02/VID_0012.MP4"


class TestPeople:
    def test_write_and_read_person(self, data_dir):
        store = DataStore(data_dir)
        store.initialize()

        person = Person(
            person_id="daughter", display_name="Lily", relationship="child",
        )
        path = store.write_person(person)
        assert os.path.exists(path)
        assert path.endswith("daughter.yaml")

        loaded = store.read_person("daughter")
        assert loaded is not None
        assert loaded.display_name == "Lily"

    def test_read_person_not_found(self, data_dir):
        store = DataStore(data_dir)
        store.initialize()
        assert store.read_person("nonexistent") is None

    def test_read_all_people(self, data_dir):
        store = DataStore(data_dir)
        store.initialize()

        store.write_person(
            Person(person_id="daughter", display_name="Lily", relationship="child"),
        )
        store.write_person(
            Person(person_id="friend_theo", display_name="Theo", relationship="friend"),
        )

        people = store.read_all_people()
        assert len(people) == 2
        names = {p.display_name for p in people}
        assert names == {"Lily", "Theo"}

    def test_read_all_people_empty(self, data_dir):
        store = DataStore(data_dir)
        store.initialize()
        assert store.read_all_people() == []

    def test_delete_person(self, data_dir):
        store = DataStore(data_dir)
        store.initialize()

        store.write_person(
            Person(person_id="test", display_name="Test", relationship="friend"),
        )
        assert store.delete_person("test") is True
        assert store.read_person("test") is None

    def test_delete_person_not_found(self, data_dir):
        store = DataStore(data_dir)
        store.initialize()
        assert store.delete_person("nonexistent") is False

    def test_write_person_with_new_fields(self, data_dir):
        store = DataStore(data_dir)
        store.initialize()

        person = Person(
            person_id="friend_theo",
            display_name="Theo",
            relationship="friend",
            close_friend=True,
            last_contact=date(2026, 2, 20),
        )
        store.write_person(person)

        loaded = store.read_person("friend_theo")
        assert loaded is not None
        assert loaded.close_friend is True
        assert loaded.last_contact == date(2026, 2, 20)


class TestPeopleMigration:
    def test_migrates_from_old_people_yaml(self, data_dir):
        store = DataStore(data_dir)
        # Create old-format people.yaml manually
        os.makedirs(data_dir, exist_ok=True)
        old_content = {
            "_schema": {"version": 1, "description": "test"},
            "people": [
                {"person_id": "daughter", "display_name": "Lily", "relationship": "child"},
                {"person_id": "friend_theo", "display_name": "Theo", "relationship": "friend"},
            ],
        }
        with open(os.path.join(data_dir, "people.yaml"), "w") as f:
            yaml.dump(old_content, f)

        store.initialize()

        # Old file should be removed
        assert not os.path.exists(os.path.join(data_dir, "people.yaml"))
        # People should exist in directory
        assert store.read_person("daughter") is not None
        assert store.read_person("friend_theo") is not None
        people = store.read_all_people()
        assert len(people) == 2

    def test_migrates_empty_people_yaml(self, data_dir):
        store = DataStore(data_dir)
        os.makedirs(data_dir, exist_ok=True)
        old_content = {"_schema": {"version": 1}, "people": []}
        with open(os.path.join(data_dir, "people.yaml"), "w") as f:
            yaml.dump(old_content, f)

        store.initialize()

        # Old file should be removed even when empty
        assert not os.path.exists(os.path.join(data_dir, "people.yaml"))
        assert store.read_all_people() == []

    def test_migration_idempotent(self, data_dir):
        store = DataStore(data_dir)
        os.makedirs(data_dir, exist_ok=True)
        old_content = {
            "_schema": {"version": 1},
            "people": [
                {"person_id": "test", "display_name": "Test", "relationship": "friend"},
            ],
        }
        with open(os.path.join(data_dir, "people.yaml"), "w") as f:
            yaml.dump(old_content, f)

        store.initialize()
        store.initialize()  # second call should not error

        assert store.read_person("test") is not None
        assert len(store.read_all_people()) == 1


class TestPreferences:
    def test_defaults(self, data_dir):
        store = DataStore(data_dir)
        store.initialize()
        prefs = store.read_preferences()
        assert prefs.nostalgia_weights.milestones == 1.0
        assert prefs.tone_preference.style == "heartfelt"

    def test_write_and_read(self, data_dir):
        store = DataStore(data_dir)
        store.initialize()
        prefs = PreferencesFile()
        prefs.nostalgia_weights.milestones = 2.0
        store.write_preferences(prefs)
        loaded = store.read_preferences()
        assert loaded.nostalgia_weights.milestones == 2.0


class TestPendingQuestions:
    def test_write_and_read(self, data_dir):
        store = DataStore(data_dir)
        store.initialize()
        pq = PendingQuestionsFile(
            questions=[
                PendingQuestion(
                    id="q_001",
                    type="person_identification",
                    subject="cluster_c_099",
                    status="pending",
                    created_at=datetime(2026, 2, 24, 15, 0, 0),
                )
            ]
        )
        store.write_pending_questions(pq)
        loaded = store.read_pending_questions()
        assert len(loaded.questions) == 1
        assert loaded.questions[0].id == "q_001"


class TestContext:
    def test_read_write_roundtrip(self, data_dir):
        store = DataStore(data_dir)
        store.initialize()

        ctx = {"family": {"members": [{"name": "Tom", "role": "Dad"}]}, "notes": ["test"]}
        store.write_context(ctx)

        loaded = store.read_context()
        assert loaded["family"]["members"][0]["name"] == "Tom"
        assert loaded["notes"] == ["test"]

    def test_preserves_schema(self, data_dir):
        store = DataStore(data_dir)
        store.initialize()

        store.write_context({"notes": ["hello"]})
        with open(os.path.join(data_dir, "context.yaml")) as f:
            raw = yaml.safe_load(f)
        assert "_schema" in raw


class TestListEvents:
    def test_empty(self, data_dir):
        store = DataStore(data_dir)
        store.initialize()
        assert store.list_events() == []

    def test_returns_all_events(self, data_dir):
        store = DataStore(data_dir)
        store.initialize()
        store.write_event(Event(
            id="20260224_park", date=date(2026, 2, 24), title="Park",
            type="daily", description="Park", people=["Lily"], source="agent",
        ))
        store.write_event(Event(
            id="20260225_school", date=date(2026, 2, 25), title="School",
            type="daily", description="School", people=["Lily"], source="agent",
        ))
        results = store.list_events()
        assert len(results) == 2
        # Newest first
        assert results[0].date >= results[1].date

    def test_filter_by_date_range(self, data_dir):
        store = DataStore(data_dir)
        store.initialize()
        store.write_event(Event(
            id="20260224_a", date=date(2026, 2, 24), title="A",
            type="daily", description="A", people=[], source="agent",
        ))
        store.write_event(Event(
            id="20260301_b", date=date(2026, 3, 1), title="B",
            type="daily", description="B", people=[], source="agent",
        ))
        results = store.list_events(date_from=date(2026, 2, 24), date_to=date(2026, 2, 28))
        assert len(results) == 1
        assert results[0].title == "A"

    def test_filter_by_people(self, data_dir):
        store = DataStore(data_dir)
        store.initialize()
        store.write_event(Event(
            id="20260224_a", date=date(2026, 2, 24), title="A",
            type="daily", description="A", people=["Lily"], source="agent",
        ))
        store.write_event(Event(
            id="20260224_b", date=date(2026, 2, 24), title="B",
            type="daily", description="B", people=["Dad"], source="agent",
        ))
        results = store.list_events(people=["Lily"])
        assert len(results) == 1
        assert results[0].title == "A"

    def test_filter_by_query(self, data_dir):
        store = DataStore(data_dir)
        store.initialize()
        store.write_event(Event(
            id="20260224_park", date=date(2026, 2, 24), title="Park day",
            type="daily", description="Went to the park", people=[], source="agent",
        ))
        store.write_event(Event(
            id="20260224_school", date=date(2026, 2, 24), title="School",
            type="daily", description="Dropped off at school", people=[], source="agent",
        ))
        results = store.list_events(query="park")
        assert len(results) == 1
        assert results[0].title == "Park day"

    def test_limit(self, data_dir):
        store = DataStore(data_dir)
        store.initialize()
        for i in range(5):
            store.write_event(Event(
                id=f"20260{i + 1:02d}01_e{i}", date=date(2026, i + 1, 1),
                title=f"Event {i}", type="daily", description="x",
                people=[], source="agent",
            ))
        results = store.list_events(limit=3)
        assert len(results) == 3


class TestFindEventById:
    def test_found(self, data_dir):
        store = DataStore(data_dir)
        store.initialize()
        store.write_event(Event(
            id="20260224_park_day", date=date(2026, 2, 24), title="Park day",
            type="daily", description="Fun", people=["Lily"], source="agent",
        ))
        event = store.find_event_by_id("20260224_park_day")
        assert event is not None
        assert event.title == "Park day"

    def test_not_found(self, data_dir):
        store = DataStore(data_dir)
        store.initialize()
        assert store.find_event_by_id("20260224_nope") is None

    def test_invalid_id(self, data_dir):
        store = DataStore(data_dir)
        store.initialize()
        assert store.find_event_by_id("bad") is None


class TestUpdateEvent:
    def test_updates_fields(self, data_dir):
        store = DataStore(data_dir)
        store.initialize()
        store.write_event(Event(
            id="20260224_park", date=date(2026, 2, 24), title="Park",
            type="daily", description="Fun", people=["Lily"], source="agent",
        ))
        updated = store.update_event("20260224_park", {"description": "So much fun!"})
        assert updated is not None
        assert updated.description == "So much fun!"

        # Verify persisted
        reloaded = store.find_event_by_id("20260224_park")
        assert reloaded is not None
        assert reloaded.description == "So much fun!"

    def test_not_found(self, data_dir):
        store = DataStore(data_dir)
        store.initialize()
        assert store.update_event("20260224_nope", {"title": "x"}) is None


class TestDeleteEvent:
    def test_deletes_existing(self, data_dir):
        store = DataStore(data_dir)
        store.initialize()
        store.write_event(Event(
            id="20260224_park", date=date(2026, 2, 24), title="Park",
            type="daily", description="Fun", people=["Lily"], source="agent",
        ))
        assert store.delete_event("20260224_park") is True
        assert store.find_event_by_id("20260224_park") is None

    def test_not_found(self, data_dir):
        store = DataStore(data_dir)
        store.initialize()
        assert store.delete_event("20260224_nope") is False

    def test_invalid_id(self, data_dir):
        store = DataStore(data_dir)
        store.initialize()
        assert store.delete_event("bad") is False


class TestAuthorizedChats:
    def test_read_write_roundtrip(self, data_dir):
        store = DataStore(data_dir)
        store.initialize()

        ac = AuthorizedChatsFile(
            chats=[AuthorizedChat(chat_id="123", status="approved")]
        )
        store.write_authorized_chats(ac)

        loaded = store.read_authorized_chats()
        assert len(loaded.chats) == 1
        assert loaded.chats[0].chat_id == "123"
        assert loaded.chats[0].status == "approved"

    def test_empty_by_default(self, data_dir):
        store = DataStore(data_dir)
        store.initialize()

        loaded = store.read_authorized_chats()
        assert loaded.chats == []

    def test_migration_from_legacy_authorized_chat_id(self, data_dir):
        store = DataStore(data_dir)
        store.initialize()

        # Set legacy authorized_chat_id
        state = DigestState(authorized_chat_id="456")
        store.write_digest_state(state)

        # Clear authorized_chats to empty
        store.write_authorized_chats(AuthorizedChatsFile(chats=[]))

        # Re-initialize should migrate
        store.initialize()

        ac = store.read_authorized_chats()
        assert len(ac.chats) == 1
        assert ac.chats[0].chat_id == "456"
        assert ac.chats[0].status == "approved"

    def test_migration_skipped_when_chats_exist(self, data_dir):
        store = DataStore(data_dir)
        store.initialize()

        # Set legacy authorized_chat_id
        state = DigestState(authorized_chat_id="456")
        store.write_digest_state(state)

        # Write an existing chat
        ac = AuthorizedChatsFile(
            chats=[AuthorizedChat(chat_id="789", status="approved")]
        )
        store.write_authorized_chats(ac)

        # Re-initialize should NOT migrate
        store.initialize()

        loaded = store.read_authorized_chats()
        assert len(loaded.chats) == 1
        assert loaded.chats[0].chat_id == "789"
