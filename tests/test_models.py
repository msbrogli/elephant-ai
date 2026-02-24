"""Tests for Pydantic data models."""

from datetime import date, datetime

import pytest
from pydantic import ValidationError

from elephant.data.models import (
    Event,
    LifeEvent,
    PendingQuestion,
    PendingQuestionsFile,
    Person,
    PersonRelationship,
    PhotoEntry,
    PreferencesFile,
    VideoEntry,
)


class TestEvent:
    def test_minimal_event(self):
        e = Event(
            id="20260224_first_steps",
            date=date(2026, 2, 24),
            title="Lily's first steps",
            type="milestone",
            description="Lily took 4 steps!",
            people=["Lily", "Dad"],
            source="WhatsApp",
        )
        assert e.nostalgia_score == 1.0
        assert e.tags == []

    def test_full_event(self):
        e = Event(
            id="20260224_first_steps",
            date=date(2026, 2, 24),
            time="14:15",
            title="Lily's first steps",
            type="milestone",
            description="Lily took 4 steps toward Dad!",
            people=["Lily", "Dad"],
            location="Portland, OR",
            media={"photos": ["2026/02/IMG_4455.JPG"], "videos": []},
            source="WhatsApp",
            nostalgia_score=1.5,
            tags=["baby", "milestone"],
        )
        assert e.media is not None
        assert e.media.photos == ["2026/02/IMG_4455.JPG"]

    def test_event_missing_required(self):
        with pytest.raises(ValidationError):
            Event(id="test", date=date(2026, 1, 1), title="t", type="daily")  # type: ignore[call-arg]


class TestPhotoEntry:
    def test_photo_entry(self):
        p = PhotoEntry(
            photo_id="2026/02/IMG_4455.JPG",
            sha256="abc123",
            taken_at=datetime(2026, 2, 24, 14, 14, 55),
            source="google_photos",
            gps={"lat": 33.15, "lon": -96.82},
            place="Portland, OR",
            people_detected=["daughter"],
            camera={"make": "Apple", "model": "iPhone 15 Pro"},
            event_id="20260224_first_steps",
        )
        assert p.gps is not None
        assert p.gps.lat == 33.15
        assert p.camera is not None
        assert p.camera.make == "Apple"


class TestVideoEntry:
    def test_video_entry(self):
        v = VideoEntry(
            video_id="2026/02/VID_0012.MP4",
            sha256="def456",
            taken_at=datetime(2026, 2, 24, 14, 15, 0),
            source="google_photos",
            duration_seconds=12.5,
        )
        assert v.duration_seconds == 12.5
        assert v.people_detected == []


class TestPeople:
    def test_person(self):
        p = Person(
            person_id="daughter",
            display_name="Lily",
            relationship="child",
            birthday=date(2023, 1, 10),
            face_clusters=["c_001", "c_042"],
        )
        assert p.display_name == "Lily"

    def test_person_defaults(self):
        p = Person(person_id="test", display_name="Test", relationship="friend")
        assert p.close_friend is False
        assert p.last_contact is None
        assert p.relationships == []
        assert p.life_events == []

    def test_close_friend_and_last_contact(self):
        p = Person(
            person_id="friend_theo",
            display_name="Theo",
            relationship="friend",
            close_friend=True,
            last_contact=date(2026, 2, 20),
        )
        assert p.close_friend is True
        assert p.last_contact == date(2026, 2, 20)

    def test_relationships(self):
        p = Person(
            person_id="friend_theo",
            display_name="Theo",
            relationship="friend",
            relationships=[
                PersonRelationship(person_id="friend_felix", label="brother"),
            ],
        )
        assert len(p.relationships) == 1
        assert p.relationships[0].label == "brother"

    def test_life_events(self):
        p = Person(
            person_id="friend_theo",
            display_name="Theo",
            relationship="friend",
            life_events=[
                LifeEvent(date=date(2026, 6, 15), description="got engaged"),
                LifeEvent(date=date(2027, 3, 1), description="wedding"),
            ],
        )
        assert len(p.life_events) == 2
        assert p.life_events[0].description == "got engaged"


class TestPreferences:
    def test_defaults(self):
        pf = PreferencesFile()
        assert pf.nostalgia_weights.milestones == 1.0
        assert pf.tone_preference.style == "heartfelt"

    def test_custom_values(self):
        pf = PreferencesFile(
            nostalgia_weights={"milestones": 1.5, "mundane_daily": 0.7},
            tone_preference={"style": "playful", "length": "long"},
        )
        assert pf.nostalgia_weights.milestones == 1.5
        assert pf.tone_preference.style == "playful"


class TestPendingQuestions:
    def test_pending_question(self):
        q = PendingQuestion(
            id="q_8821",
            type="person_identification",
            subject="cluster_c_099",
            status="pending",
            created_at=datetime(2026, 2, 24, 15, 0, 0),
        )
        assert q.question is None

    def test_pending_questions_file(self):
        pqf = PendingQuestionsFile(
            questions=[
                PendingQuestion(
                    id="q_001",
                    type="event_enrichment",
                    subject="20260224_first_steps",
                    question="Was she walking toward someone?",
                    status="asked",
                    created_at=datetime(2026, 2, 24, 15, 30, 0),
                ),
            ]
        )
        assert len(pqf.questions) == 1
        assert pqf.questions[0].question is not None
