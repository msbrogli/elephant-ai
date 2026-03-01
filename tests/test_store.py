"""Tests for DataStore."""

import os
from datetime import date, datetime

import yaml

from elephant.data.models import (
    AuthorizedChat,
    AuthorizedChatsFile,
    Memory,
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
        assert os.path.isdir(os.path.join(data_dir, "memories"))
        assert os.path.isdir(os.path.join(data_dir, "photo_index"))
        assert os.path.isdir(os.path.join(data_dir, "video_index"))
        assert os.path.isdir(os.path.join(data_dir, "people"))
        assert os.path.isdir(os.path.join(data_dir, "faces"))
        assert os.path.isdir(os.path.join(data_dir, "logs"))

    def test_deploys_dir_schemas(self, data_dir):
        store = DataStore(data_dir)
        store.initialize()
        for schema_path in [
            os.path.join(data_dir, "memories", "_schema.yaml"),
            os.path.join(data_dir, "people", "_schema.yaml"),
        ]:
            assert os.path.exists(schema_path)
            with open(schema_path) as f:
                data = yaml.safe_load(f)
            assert data["version"] == 1

    def test_deploys_single_file_schemas(self, data_dir):
        store = DataStore(data_dir)
        store.initialize()
        for name in ["preferences.yaml", "pending_questions.yaml"]:
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


class TestMemories:
    def test_write_and_read_memory(self, data_dir):
        store = DataStore(data_dir)
        store.initialize()
        memory = Memory(
            id="20260224_first_steps",
            date=date(2026, 2, 24),
            time="14:15",
            title="Lily's first steps",
            type="milestone",
            description="Lily took 4 steps!",
            people=["Lily", "Dad"],
            source="WhatsApp",
        )
        path = store.write_memory(memory)
        assert os.path.exists(path)
        assert "2026/02/20260224_first_steps.yaml" in path

        loaded = store.read_memory(path)
        assert loaded.id == memory.id
        assert loaded.title == memory.title
        assert loaded.people == memory.people


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
        )
        store.write_person(person)

        loaded = store.read_person("friend_theo")
        assert loaded is not None
        assert loaded.close_friend is True



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


class TestListMemories:
    def test_empty(self, data_dir):
        store = DataStore(data_dir)
        store.initialize()
        assert store.list_memories() == []

    def test_returns_all_memories(self, data_dir):
        store = DataStore(data_dir)
        store.initialize()
        store.write_memory(Memory(
            id="20260224_park", date=date(2026, 2, 24), title="Park",
            type="daily", description="Park", people=["Lily"], source="agent",
        ))
        store.write_memory(Memory(
            id="20260225_school", date=date(2026, 2, 25), title="School",
            type="daily", description="School", people=["Lily"], source="agent",
        ))
        results = store.list_memories()
        assert len(results) == 2
        # Newest first
        assert results[0].date >= results[1].date

    def test_filter_by_date_range(self, data_dir):
        store = DataStore(data_dir)
        store.initialize()
        store.write_memory(Memory(
            id="20260224_a", date=date(2026, 2, 24), title="A",
            type="daily", description="A", people=[], source="agent",
        ))
        store.write_memory(Memory(
            id="20260301_b", date=date(2026, 3, 1), title="B",
            type="daily", description="B", people=[], source="agent",
        ))
        results = store.list_memories(date_from=date(2026, 2, 24), date_to=date(2026, 2, 28))
        assert len(results) == 1
        assert results[0].title == "A"

    def test_filter_by_people(self, data_dir):
        store = DataStore(data_dir)
        store.initialize()
        store.write_memory(Memory(
            id="20260224_a", date=date(2026, 2, 24), title="A",
            type="daily", description="A", people=["Lily"], source="agent",
        ))
        store.write_memory(Memory(
            id="20260224_b", date=date(2026, 2, 24), title="B",
            type="daily", description="B", people=["Dad"], source="agent",
        ))
        results = store.list_memories(people=["Lily"])
        assert len(results) == 1
        assert results[0].title == "A"

    def test_filter_by_query(self, data_dir):
        store = DataStore(data_dir)
        store.initialize()
        store.write_memory(Memory(
            id="20260224_park", date=date(2026, 2, 24), title="Park day",
            type="daily", description="Went to the park", people=[], source="agent",
        ))
        store.write_memory(Memory(
            id="20260224_school", date=date(2026, 2, 24), title="School",
            type="daily", description="Dropped off at school", people=[], source="agent",
        ))
        results = store.list_memories(query="park")
        assert len(results) == 1
        assert results[0].title == "Park day"

    def test_limit(self, data_dir):
        store = DataStore(data_dir)
        store.initialize()
        for i in range(5):
            store.write_memory(Memory(
                id=f"20260{i + 1:02d}01_m{i}", date=date(2026, i + 1, 1),
                title=f"Memory {i}", type="daily", description="x",
                people=[], source="agent",
            ))
        results = store.list_memories(limit=3)
        assert len(results) == 3


class TestFindMemoryById:
    def test_found(self, data_dir):
        store = DataStore(data_dir)
        store.initialize()
        store.write_memory(Memory(
            id="20260224_park_day", date=date(2026, 2, 24), title="Park day",
            type="daily", description="Fun", people=["Lily"], source="agent",
        ))
        memory = store.find_memory_by_id("20260224_park_day")
        assert memory is not None
        assert memory.title == "Park day"

    def test_not_found(self, data_dir):
        store = DataStore(data_dir)
        store.initialize()
        assert store.find_memory_by_id("20260224_nope") is None

    def test_invalid_id(self, data_dir):
        store = DataStore(data_dir)
        store.initialize()
        assert store.find_memory_by_id("bad") is None


class TestUpdateMemory:
    def test_updates_fields(self, data_dir):
        store = DataStore(data_dir)
        store.initialize()
        store.write_memory(Memory(
            id="20260224_park", date=date(2026, 2, 24), title="Park",
            type="daily", description="Fun", people=["Lily"], source="agent",
        ))
        updated = store.update_memory("20260224_park", {"description": "So much fun!"})
        assert updated is not None
        assert updated.description == "So much fun!"

        # Verify persisted
        reloaded = store.find_memory_by_id("20260224_park")
        assert reloaded is not None
        assert reloaded.description == "So much fun!"

    def test_not_found(self, data_dir):
        store = DataStore(data_dir)
        store.initialize()
        assert store.update_memory("20260224_nope", {"title": "x"}) is None


class TestDeleteMemory:
    def test_deletes_existing(self, data_dir):
        store = DataStore(data_dir)
        store.initialize()
        store.write_memory(Memory(
            id="20260224_park", date=date(2026, 2, 24), title="Park",
            type="daily", description="Fun", people=["Lily"], source="agent",
        ))
        assert store.delete_memory("20260224_park") is True
        assert store.find_memory_by_id("20260224_park") is None

    def test_not_found(self, data_dir):
        store = DataStore(data_dir)
        store.initialize()
        assert store.delete_memory("20260224_nope") is False

    def test_invalid_id(self, data_dir):
        store = DataStore(data_dir)
        store.initialize()
        assert store.delete_memory("bad") is False


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

