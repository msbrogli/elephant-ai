# Data Types Reference

All data is stored as YAML files under `$DATA_DIR/`. There are two storage patterns:

- **Directory-based**: one YAML file per record, with a `_schema.yaml` file describing the format.
- **Single-file**: one YAML file containing all records, with an embedded `_schema` block.

---

## Directory-based stores

### Events (`events/`)

One file per event, organized by `YYYY/MM/YYYYMMDD_slug.yaml`.

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| `id` | string | yes | Unique ID matching filename (e.g. `20260224_first_steps`) |
| `date` | date | yes | Event date (`YYYY-MM-DD`) |
| `time` | string | no | Event time (`HH:MM`, 24h) |
| `title` | string | yes | Short human-readable title |
| `type` | string | yes | `milestone`, `daily`, `outing`, `celebration`, `health`, `travel`, `mundane`, `other` |
| `description` | string | yes | Free-text description |
| `people` | list[string] | yes | Display names of people involved |
| `location` | string | no | Human-readable location |
| `media` | object | no | `photos` and `videos` lists of relative paths |
| `source` | string | yes | `WhatsApp`, `Telegram`, `evening_checkin`, `morning_digest`, `manual`, `photo_ingest`, `agent` |
| `nostalgia_score` | float | no | Weight for digest ranking (default 1.0, higher = more likely to surface) |
| `tags` | list[string] | no | Freeform tags |

**How events are created:**
- Telegram messages parsed by the LLM into structured events
- Conversational agent `create_event` tool
- Batch import from files (JSON, CSV) via `describe_attachment` + LLM parsing
- Evening check-in flow

---

### People (`people/`)

One file per person: `people/{person_id}.yaml`.

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| `person_id` | string | yes | Stable identifier (e.g. `daughter`, `friend_theo`) |
| `display_name` | string | yes | Name shown in digests and logs |
| `relationship` | string | yes | Relationship to user (e.g. `child`, `spouse`, `friend`) |
| `birthday` | date | no | Birthday (`YYYY-MM-DD`) |
| `close_friend` | bool | no | Close friends get earlier birthday reminders (21 days vs day-of) |
| `last_contact` | date | no | Auto-updated when an event mentions this person |
| `relationships` | list[object] | no | Connections to other people (see below) |
| `life_events` | list[object] | no | Notable life events (see below) |
| `face_clusters` | list[string] | no | Face cluster IDs from recognition system |
| `notes` | string | no | Freeform notes |

**`relationships` items:**

| Field | Type | Description |
|-------|------|-------------|
| `person_id` | string | `person_id` of the related person |
| `label` | string | Relationship label (e.g. `brother`, `spouse`, `parent`) |

Example: Theo's file might have `relationships: [{person_id: friend_felix, label: brother}]`

**`life_events` items:**

| Field | Type | Description |
|-------|------|-------------|
| `date` | date | Date of the life event |
| `description` | string | What happened (e.g. `got engaged`, `wedding`, `moved to Austin`) |

**How people are tracked:**
- Created via context updates or the conversational agent
- `close_friend` flag enables 3-week birthday reminder window
- `last_contact` is auto-updated when `create_event` mentions a person by name (only if the event date is more recent than the current value, to avoid backdating historical events)
- `relationships` maps connections between people (e.g. "Theo's brother is Felix")
- `life_events` tracks notable happenings in a friend's life (engagement, wedding, trips, etc.)

**How birthdays surface in digests:**
- Close friends: included in morning digest if birthday is within 21 days
  - 15-21 days: "birthday coming up"
  - 8-14 days: "start thinking about a gift"
  - 1-7 days: "finalize gift plans!"
  - Day-of: "TODAY is X's birthday!"
- Non-close-friends: only mentioned on the day itself
- Feb 29 birthdays: treated as Mar 1 in non-leap years
- If no events match today but birthdays exist, a birthday-focused digest is sent instead of falling back to questions

---

### Photo Index (`photo_index/`)

One file per date: `photo_index/YYYY/MM/YYYY-MM-DD.yaml`. Each file contains a list of photo entries.

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| `photo_id` | string | yes | Relative path under `media/photos/` |
| `sha256` | string | yes | SHA-256 hash for dedup |
| `taken_at` | datetime | yes | ISO 8601 timestamp from EXIF |
| `source` | string | yes | `google_photos`, `apple_photos`, `local_folder`, `manual` |
| `gps` | object | no | `lat`, `lon` from EXIF |
| `place` | string | no | Reverse-geocoded place name |
| `people_detected` | list[string] | no | `person_id` values matched via face recognition |
| `camera` | object | no | `make`, `model` from EXIF |
| `event_id` | string | no | Linked event ID |

---

### Video Index (`video_index/`)

One file per date: `video_index/YYYY/MM/YYYY-MM-DD.yaml`. Same structure as photo index plus:

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| `video_id` | string | yes | Relative path under `media/videos/` |
| `duration_seconds` | float | no | Video duration |
| `thumbnail` | string | no | Path to auto-generated thumbnail |

(All other fields match photo index.)

---

## Single-file stores

### Context (`context.yaml`)

Free-form family context loaded into every LLM prompt.

| Section | Description |
|---------|-------------|
| `family.members` | Core family members: `name`, `role`, `birthday?`, `employer?` |
| `friends` | Close friends: `name`, `relationship`, `met_at?` |
| `locations` | Key locations as `name -> description` |
| `notes` | Freeform facts (with date stamp) |

---

### Preferences (`preferences.yaml`)

| Field | Type | Default | Description |
|-------|------|---------|-------------|
| `nostalgia_weights.milestones` | float | 1.0 | Weight for milestone events |
| `nostalgia_weights.mundane_daily` | float | 1.0 | Weight for everyday moments |
| `nostalgia_weights.people_focus` | float | 1.0 | Boost for events with many people |
| `nostalgia_weights.location_focus` | float | 1.0 | Boost for events at special places |
| `tone_preference.style` | string | `heartfelt` | `heartfelt`, `playful`, `factual` |
| `tone_preference.length` | string | `short` | `short`, `medium`, `long` |

---

### Pending Questions (`pending_questions.yaml`)

Queue of questions the system wants to ask the user.

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| `id` | string | yes | Unique question ID (e.g. `q_8821`) |
| `type` | string | yes | `person_identification`, `event_enrichment`, `context_gap`, `media_linking` |
| `subject` | string | yes | Reference to what needs clarification |
| `question` | string | no | Question text (generated by LLM if missing) |
| `status` | string | yes | `pending`, `asked`, `answered`, `dismissed` |
| `created_at` | datetime | yes | When the question was created |
| `answered_at` | datetime | no | When answered |
| `answer` | string | no | User's reply text |
| `message_id` | string | no | Telegram message ID for reply tracking |

---

### Digest State (`digest_state.yaml`)

Tracks the last digest sent.

| Field | Type | Description |
|-------|------|-------------|
| `last_digest_sent_at` | datetime | When the last digest was sent |
| `last_digest_event_ids` | list[string] | Event IDs included in the last digest |
| `last_digest_message_id` | string | Message ID for reply tracking |
| `authorized_chat_id` | string | (Legacy) migrated to `authorized_chats.yaml` |

---

### Authorized Chats (`authorized_chats.yaml`)

Telegram chats authorized to interact with the bot.

| Field | Type | Description |
|-------|------|-------------|
| `chat_id` | string | Telegram chat ID |
| `status` | string | `approved` or `pending` |
| `added_at` | datetime | When authorized |
| `display_name` | string | Chat display name |
