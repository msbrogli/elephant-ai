"""Pydantic models for all YAML document types."""

from datetime import date, datetime

from pydantic import BaseModel, Field

# --- Shared sub-models ---


class MediaLinks(BaseModel):
    photos: list[str] = Field(default_factory=list)
    videos: list[str] = Field(default_factory=list)


class GPSCoords(BaseModel):
    lat: float
    lon: float


class CameraInfo(BaseModel):
    make: str = ""
    model: str = ""


# --- Event ---


class Event(BaseModel):
    id: str
    date: date
    time: str | None = None
    title: str
    type: str  # milestone, daily, outing, celebration, health, travel, mundane, other
    description: str
    people: list[str]
    location: str | None = None
    media: MediaLinks | None = None
    source: str  # WhatsApp, Telegram, evening_checkin, morning_digest, manual, photo_ingest
    nostalgia_score: float = 1.0
    tags: list[str] = Field(default_factory=list)


# --- Photo Index ---


class PhotoEntry(BaseModel):
    photo_id: str
    sha256: str
    taken_at: datetime
    source: str  # google_photos, apple_photos, local_folder, manual
    gps: GPSCoords | None = None
    place: str | None = None
    people_detected: list[str] = Field(default_factory=list)
    camera: CameraInfo | None = None
    event_id: str | None = None


# --- Video Index ---


class VideoEntry(BaseModel):
    video_id: str
    sha256: str
    taken_at: datetime
    duration_seconds: float | None = None
    source: str  # google_photos, apple_photos, local_folder, manual
    gps: GPSCoords | None = None
    place: str | None = None
    people_detected: list[str] = Field(default_factory=list)
    camera: CameraInfo | None = None
    thumbnail: str | None = None
    event_id: str | None = None


# --- People ---


class PersonRelationship(BaseModel):
    person_id: str
    label: str  # e.g. "brother", "spouse", "parent"


class LifeEvent(BaseModel):
    date: date
    description: str  # e.g. "got engaged", "wedding", "moved to Austin"


class Person(BaseModel):
    person_id: str
    display_name: str
    relationship: str
    birthday: date | None = None
    close_friend: bool = False
    last_contact: date | None = None
    relationships: list[PersonRelationship] = Field(default_factory=list)
    life_events: list[LifeEvent] = Field(default_factory=list)
    face_clusters: list[str] = Field(default_factory=list)
    notes: str | None = None


# --- Preferences ---


class NostalgiaWeights(BaseModel):
    milestones: float = 1.0
    mundane_daily: float = 1.0
    people_focus: float = 1.0
    location_focus: float = 1.0


class TonePreference(BaseModel):
    style: str = "heartfelt"  # heartfelt, playful, factual
    length: str = "short"  # short, medium, long


class PreferencesFile(BaseModel):
    nostalgia_weights: NostalgiaWeights = NostalgiaWeights()
    tone_preference: TonePreference = TonePreference()


# --- Pending Questions ---


class PendingQuestion(BaseModel):
    id: str
    type: str  # person_identification, event_enrichment, context_gap, media_linking
    subject: str
    question: str | None = None
    status: str = "pending"  # pending, asked, answered, dismissed
    created_at: datetime
    answered_at: datetime | None = None
    answer: str | None = None
    message_id: str | None = None


class PendingQuestionsFile(BaseModel):
    questions: list[PendingQuestion] = Field(default_factory=list)


# --- Digest State ---


class DigestState(BaseModel):
    last_digest_sent_at: datetime | None = None
    last_digest_event_ids: list[str] = Field(default_factory=list)
    last_digest_message_id: str | None = None
    authorized_chat_id: str | None = None


# --- Authorized Chats ---


class AuthorizedChat(BaseModel):
    chat_id: str
    status: str = "approved"  # "approved" | "pending"
    added_at: datetime | None = None
    display_name: str | None = None


class AuthorizedChatsFile(BaseModel):
    chats: list[AuthorizedChat] = Field(default_factory=list)
