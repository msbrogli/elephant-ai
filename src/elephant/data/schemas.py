"""Raw YAML schema content as constants, sourced from DESIGN.md."""

EVENTS_SCHEMA = """\
version: 1
description: "Each file represents one memory event. Filename: {YYYYMMDD}_{slug}.yaml"
fields:
  id:
    type: string
    required: true
    description: "Unique ID matching the filename without extension (e.g. 20260224_first_steps)"
  date:
    type: date
    required: true
    description: "Event date in YYYY-MM-DD format"
  time:
    type: string
    required: false
    description: "Event time in HH:MM format (24h). Omit if unknown."
  title:
    type: string
    required: true
    description: "Short human-readable title"
  type:
    type: string
    required: true
    enum: [milestone, daily, outing, celebration, health, travel, mundane, other]
    description: "Event category"
  description:
    type: string
    required: true
    description: "Free-text description of what happened"
  people:
    type: list[string]
    required: true
    description: "Display names of people involved"
  location:
    type: string
    required: false
    description: "Human-readable location (e.g. 'Portland, OR')"
  media:
    type: object
    required: false
    description: "Linked media files"
    fields:
      photos:
        type: list[string]
        description: "Relative paths under /app/media/photos/"
      videos:
        type: list[string]
        description: "Relative paths under /app/media/videos/"
  source:
    type: string
    required: true
    enum: [WhatsApp, Telegram, evening_checkin, morning_digest, manual, photo_ingest]
    description: "How this event was captured"
  nostalgia_score:
    type: float
    required: false
    default: 1.0
    description: "Weight for morning digest ranking. Higher = more likely to surface."
  tags:
    type: list[string]
    required: false
    default: []
    description: "Freeform tags for filtering"
"""

PHOTO_INDEX_SCHEMA = """\
version: 1
description: "Each file contains a list of photos ingested on that day. Filename: {YYYY-MM-DD}.yaml"
item_type: list
fields:
  photo_id:
    type: string
    required: true
    description: "Relative path under /app/media/photos/ (e.g. '2026/02/IMG_4455.JPG')"
  sha256:
    type: string
    required: true
    description: "SHA-256 hash for deduplication"
  taken_at:
    type: datetime
    required: true
    description: "ISO 8601 timestamp from EXIF (e.g. '2026-02-24T14:14:55')"
  source:
    type: string
    required: true
    enum: [google_photos, apple_photos, local_folder, manual]
    description: "Where the photo was imported from"
  gps:
    type: object
    required: false
    description: "GPS coordinates from EXIF"
    fields:
      lat:
        type: float
        description: "Latitude"
      lon:
        type: float
        description: "Longitude"
  place:
    type: string
    required: false
    description: "Reverse-geocoded place name. Null if geocoding failed or no GPS."
  people_detected:
    type: list[string]
    required: false
    default: []
    description: "person_id values from people.yaml matched via face recognition"
  camera:
    type: object
    required: false
    description: "Camera metadata from EXIF"
    fields:
      make:
        type: string
        description: "Camera manufacturer"
      model:
        type: string
        description: "Camera model"
  event_id:
    type: string
    required: false
    description: "Linked event ID if auto-matched or manually linked"
"""

VIDEO_INDEX_SCHEMA = """\
version: 1
description: "Each file contains a list of videos ingested on that day. Filename: {YYYY-MM-DD}.yaml"
item_type: list
fields:
  video_id:
    type: string
    required: true
    description: "Relative path under /app/media/videos/ (e.g. '2026/02/VID_0012.MP4')"
  sha256:
    type: string
    required: true
    description: "SHA-256 hash for deduplication"
  taken_at:
    type: datetime
    required: true
    description: "ISO 8601 timestamp from EXIF or file metadata"
  duration_seconds:
    type: float
    required: false
    description: "Video duration in seconds"
  source:
    type: string
    required: true
    enum: [google_photos, apple_photos, local_folder, manual]
  gps:
    type: object
    required: false
    fields:
      lat:
        type: float
      lon:
        type: float
  place:
    type: string
    required: false
  people_detected:
    type: list[string]
    required: false
    default: []
  camera:
    type: object
    required: false
    fields:
      make:
        type: string
      model:
        type: string
  thumbnail:
    type: string
    required: false
    description: "Relative path to auto-generated thumbnail image"
  event_id:
    type: string
    required: false
    description: "Linked event ID"
"""

PEOPLE_SCHEMA = """\
_schema:
  version: 1
  description: "List of known people. Used for face matching and display names."
  fields:
    person_id:
      type: string
      required: true
      description: "Stable identifier (e.g. 'daughter', 'cousin_lucas')"
    display_name:
      type: string
      required: true
      description: "Human-readable name shown in digests and logs"
    relationship:
      type: string
      required: true
      description: "Relationship to the user (e.g. 'child', 'spouse', 'friend', 'cousin')"
    birthday:
      type: date
      required: false
      description: "Birthday in YYYY-MM-DD format"
    face_clusters:
      type: list[string]
      required: false
      default: []
      description: "Face cluster IDs from recognition system"
    notes:
      type: string
      required: false
      description: "Freeform notes about this person"

people: []
"""

PEOPLE_DIR_SCHEMA = """\
version: 1
description: "Each file represents one known person. Filename: {person_id}.yaml"
fields:
  person_id:
    type: string
    required: true
    description: "Stable identifier (e.g. 'daughter', 'cousin_lucas')"
  display_name:
    type: string
    required: true
    description: "Human-readable name shown in digests and logs"
  relationship:
    type: string
    required: true
    description: "Relationship to the user (e.g. 'child', 'spouse', 'friend', 'cousin')"
  birthday:
    type: date
    required: false
    description: "Birthday in YYYY-MM-DD format"
  close_friend:
    type: boolean
    required: false
    default: false
    description: "Whether this person is a close friend (gets earlier birthday reminders)"
  last_contact:
    type: date
    required: false
    description: "Date of last recorded interaction with this person"
  relationships:
    type: list[object]
    required: false
    default: []
    description: "Connections to other known people"
    fields:
      person_id:
        type: string
        description: "person_id of the related person"
      label:
        type: string
        description: "Relationship label (e.g. 'brother', 'spouse', 'parent')"
  life_events:
    type: list[object]
    required: false
    default: []
    description: "Notable life events for this person"
    fields:
      date:
        type: date
        description: "Date of the life event"
      description:
        type: string
        description: "What happened (e.g. 'got engaged', 'wedding', 'moved to Austin')"
  face_clusters:
    type: list[string]
    required: false
    default: []
    description: "Face cluster IDs from recognition system"
  notes:
    type: string
    required: false
    description: "Freeform notes about this person"
"""

CONTEXT_SCHEMA = """\
_schema:
  version: 1
  description: "Family context loaded into every LLM prompt. Keep concise."
  sections:
    family.members:
      description: "Core family members"
      fields:
        name: "string"
        role: "string"
        birthday: "date?"
        employer: "string?"
    friends:
      description: "Close friends and their context"
      fields:
        name: "string"
        relationship: "string"
        met_at: "string?"
    locations:
      description: "Key locations as name -> address/description"
    notes:
      description: "Freeform facts the LLM should know"

family:
  members: []
friends: []
locations: {}
notes: []
"""

PREFERENCES_SCHEMA = """\
_schema:
  version: 1
  description: "User preferences learned from feedback. Weights adjust over time."
  fields:
    nostalgia_weights:
      type: object
      description: "Multipliers for event scoring in morning digest"
      fields:
        milestones: {type: float, default: 1.0, description: "Weight for milestone events"}
        mundane_daily: {type: float, default: 1.0, description: "Weight for everyday moments"}
        people_focus: {type: float, default: 1.0, description: "Boost for events with many people"}
        location_focus:
          type: float
          default: 1.0
          description: "Boost for events at special places"
    tone_preference:
      type: object
      fields:
        style: {type: string, enum: [heartfelt, playful, factual], default: heartfelt}
        length: {type: string, enum: [short, medium, long], default: short}

nostalgia_weights:
  milestones: 1.0
  mundane_daily: 1.0
  people_focus: 1.0
  location_focus: 1.0
tone_preference:
  style: heartfelt
  length: short
"""

DIGEST_STATE_SCHEMA = """\
_schema:
  version: 1
  description: "Tracks the last digest sent and its contents."
  fields:
    last_digest_sent_at:
      type: datetime
      required: false
      description: "ISO 8601 timestamp of when the last digest was sent"
    last_digest_event_ids:
      type: list[string]
      required: false
      default: []
      description: "Event IDs included in the last digest"
    last_digest_message_id:
      type: string
      required: false
      description: "Message ID of the last digest sent (for reply tracking)"
    authorized_chat_id:
      type: string
      required: false
      description: "Telegram chat ID authorized via /start command"

last_digest_sent_at: null
last_digest_event_ids: []
last_digest_message_id: null
authorized_chat_id: null
"""

AUTHORIZED_CHATS_SCHEMA = """\
_schema:
  version: 1
  description: "Authorized Telegram chats with approval status."
chats: []
"""

PENDING_QUESTIONS_SCHEMA = """\
_schema:
  version: 1
  description: >-
    Queue of questions the system wants to ask the user.
    Prevents asking too many at once.
  fields:
    id:
      type: string
      required: true
      description: "Unique question ID (e.g. 'q_8821')"
    type:
      type: string
      required: true
      enum: [person_identification, event_enrichment, context_gap, media_linking]
      description: "Category of clarification needed"
    subject:
      type: string
      required: true
      description: "Reference to what needs clarification (cluster ID, event ID, etc.)"
    question:
      type: string
      required: false
      description: "The actual question text to send. Generated by LLM if not provided."
    status:
      type: string
      required: true
      enum: [pending, asked, answered, dismissed]
      default: pending
    created_at:
      type: datetime
      required: true
    answered_at:
      type: datetime
      required: false
    answer:
      type: string
      required: false
      description: "User's reply text"

questions: []
"""

# Mapping of directory schema files to their content
DIR_SCHEMAS: dict[str, str] = {
    "events/_schema.yaml": EVENTS_SCHEMA,
    "photo_index/_schema.yaml": PHOTO_INDEX_SCHEMA,
    "video_index/_schema.yaml": VIDEO_INDEX_SCHEMA,
    "people/_schema.yaml": PEOPLE_DIR_SCHEMA,
}

# Mapping of single-file stores to their initial content (includes _schema block)
SINGLE_FILE_SCHEMAS: dict[str, str] = {
    "context.yaml": CONTEXT_SCHEMA,
    "preferences.yaml": PREFERENCES_SCHEMA,
    "pending_questions.yaml": PENDING_QUESTIONS_SCHEMA,
    "digest_state.yaml": DIGEST_STATE_SCHEMA,
    "authorized_chats.yaml": AUTHORIZED_CHATS_SCHEMA,
}
