### 🐘 Project: My Little Elephant
**A Personal Memory & Daily Digest System — Complete Master Blueprint**

---

### 1. Vision

**My Little Elephant** is a private, self-hosted, AI-powered family memory assistant. It captures life events, indexes family photos and videos, learns your preferences, and delivers warm nostalgic daily digests via WhatsApp or Telegram. It costs roughly **$5–$12/month** to run and stores everything in human-readable files backed by Git.

---

### 2. System Architecture & Deployment

The system runs in a **Docker container** on a home server, NAS, or cloud VPS. All persistent data lives on the **host machine** via mount points, so the container can be rebuilt at any time without data loss.

#### Docker Mount Points

| Host Path | Container Path | Content |
| :--- | :--- | :--- |
| `/data/elephant` | `/app/data` | YAML files, Git repo, logs, face JSON |
| `/media/library` | `/app/media` | Photo/video blobs (never in Git) |
| `/config` | `/app/config` | `config.yaml` — API keys & secrets (read-only) |

#### `docker-compose.yml`
```yaml
version: "3.9"
services:
  my_little_elephant:
    build: .
    container_name: my_little_elephant
    restart: unless-stopped
    volumes:
      - /data/elephant:/app/data
      - /media/library:/app/media
      - /config:/app/config:ro
    environment:
      - TZ=America/Chicago
      - CONFIG_PATH=/app/config/config.yaml
    ports:
      - "8080:8080"
    healthcheck:
      test: ["CMD", "curl", "-f", "http://localhost:8080/health"]
      interval: 60s
      timeout: 5s
      retries: 3
```

#### `Dockerfile`
```dockerfile
FROM python:3.12-slim
RUN apt-get update && apt-get install -y git curl wget
RUN wget -qO /usr/local/bin/yq \
    https://github.com/mikefarah/yq/releases/latest/download/yq_linux_amd64 \
    && chmod +x /usr/local/bin/yq
WORKDIR /app
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt
COPY src/ ./src/
RUN git config --global user.name "My Little Elephant" \
    && git config --global user.email "elephant@family.local"
CMD ["python", "src/main.py"]
```

---

### 3. File & Folder Structure

```
/app/data/
  events/                          # one YAML file per event
    _schema.yaml                   # schema definition for event files
    YYYY/MM/
      YYYYMMDD_slug.yaml           # e.g. 20260224_first_steps.yaml
  photo_index/                     # one YAML file per day of ingested photos
    _schema.yaml                   # schema definition for photo index files
    YYYY/MM/
      YYYY-MM-DD.yaml              # e.g. 2026-02-24.yaml
  video_index/                     # one YAML file per day of ingested videos
    _schema.yaml                   # schema definition for video index files
    YYYY/MM/
      YYYY-MM-DD.yaml
  people.yaml                      # single file — small, rarely changes
  context.yaml                     # single file — family knowledge base
  preferences.yaml                 # single file — learning weights
  pending_questions.yaml           # single file — clarification queue
  faces/
    IMG_1234.faces.json
  logs/
    app.log
    interactions.log
  .git/
  .gitignore

/app/media/
  photos/YYYY/MM/
  videos/YYYY/MM/

/app/config/
  config.yaml
```

#### File Naming Conventions
- **Events:** `{YYYYMMDD}_{slug}.yaml` — slug is a short kebab-case summary (e.g., `20260224_first_steps.yaml`)
- **Photo index:** `{YYYY-MM-DD}.yaml` — one file per day containing all photos ingested that day
- **Video index:** `{YYYY-MM-DD}.yaml` — same as photo index but for videos
- **Shared files** (`people.yaml`, `context.yaml`, `preferences.yaml`) remain single files since they are small and rarely written to concurrently. Writes to shared files use atomic replacement (write to temp file, then rename) to prevent corruption.

#### `.gitignore`
```
/app/media/
*.jpg
*.jpeg
*.png
*.mp4
*.mov
embeddings/
```

---

### 4. Data Schema (YAML)

Each data directory contains a `_schema.yaml` file that defines the expected fields, types, and constraints for data files in that directory. The LLM reads the schema before writing new files and can also update the schema as the system evolves. Single-file stores embed their schema under a top-level `_schema` key.

#### Schema Convention
- **Split files** (events, photo_index, video_index): Schema lives in `_schema.yaml` at the directory root. Data files do not repeat the schema.
- **Single files** (people, context, preferences, pending_questions): Schema is the first key (`_schema`) in the file itself.
- **Schema version**: Each schema has a `version` field. When the schema changes, bump the version. The system can still read older files — missing fields use defaults.

---

#### `events/_schema.yaml`
```yaml
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
```

**Example:** `events/2026/02/20260224_first_steps.yaml`
```yaml
id: 20260224_first_steps
date: 2026-02-24
time: "14:15"
title: "Lily's first steps"
type: milestone
description: "Lily took 4 steps toward Dad in the living room!"
people: ["Lily", "Dad"]
location: "Portland, OR"
media:
  photos: ["2026/02/IMG_4455.JPG"]
  videos: ["2026/02/VID_0012.MP4"]
source: "WhatsApp"
nostalgia_score: 1.5
tags: ["baby", "milestone"]
```

---

#### `photo_index/_schema.yaml`
```yaml
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
```

**Example:** `photo_index/2026/02/2026-02-24.yaml`
```yaml
- photo_id: "2026/02/IMG_4455.JPG"
  sha256: "e3b0c442..."
  taken_at: "2026-02-24T14:14:55"
  source: "google_photos"
  gps: {lat: 33.1507, lon: -96.8236}
  place: "Portland, OR"
  people_detected: ["daughter"]
  camera: {make: "Apple", model: "iPhone 15 Pro"}
  event_id: "20260224_first_steps"
```

---

#### `video_index/_schema.yaml`
```yaml
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
```

---

#### `people.yaml` — The Identity Store
```yaml
_schema:
  version: 1
  description: "List of known people. Used for face matching and display names."
  fields:
    person_id:
      type: string
      required: true
      description: "Stable identifier (e.g. 'daughter', 'cousin_rafael')"
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

people:
  - person_id: daughter
    display_name: "Lily"
    relationship: "child"
    birthday: "2023-01-10"
    face_clusters: ["c_001", "c_042"]
  - person_id: cousin_rafael
    display_name: "Rafael"
    relationship: "cousin"
    notes: "Visiting from Brazil"
```

---

#### `context.yaml` — The Knowledge Base
This file is the LLM's "briefing document." It is loaded with every LLM call so the system understands who people are and why they matter.
```yaml
_schema:
  version: 1
  description: "Family context loaded into every LLM prompt. Keep concise."
  sections:
    family.members:
      description: "Core family members"
      fields: {name: string, role: string, birthday: date?, employer: string?}
    friends:
      description: "Close friends and their context"
      fields: {name: string, relationship: string, met_at: string?}
    locations:
      description: "Key locations as name → address/description"
    notes:
      description: "Freeform facts the LLM should know"

family:
  members:
    - name: "Tom"
      role: "Dad / Self"
      birthday: "1985-06-15"
      employer: "Acme Corp"
    - name: "Wife"
      role: "Mom"
      birthday: "1987-09-20"
    - name: "Lily"
      role: "Daughter"
      birthday: "2023-01-10"
friends:
  - name: "John Doe"
    relationship: "College friend"
    met_at: "State University"
locations:
  home: "Portland, OR"
  work: "Remote"
notes:
  - "Family owns a minivan."
  - "Rafael is a cousin visiting from Brazil."
```

---

#### `preferences.yaml` — The Learning Store
Updated automatically based on your feedback reactions.
```yaml
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
        location_focus: {type: float, default: 1.0, description: "Boost for events at special places"}
    tone_preference:
      type: object
      fields:
        style: {type: string, enum: [heartfelt, playful, factual], default: heartfelt}
        length: {type: string, enum: [short, medium, long], default: short}

nostalgia_weights:
  milestones: 1.5
  mundane_daily: 0.7
  people_focus: 1.2
  location_focus: 0.8
tone_preference:
  style: "heartfelt"
  length: "short"
```

---

#### `pending_questions.yaml` — The Clarification Queue
```yaml
_schema:
  version: 1
  description: "Queue of questions the system wants to ask the user. Prevents asking too many at once."
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

questions:
  - id: q_8821
    type: "person_identification"
    subject: "cluster_c_099"
    status: "pending"
    created_at: "2026-02-24T15:00:00"
  - id: q_8822
    type: "event_enrichment"
    subject: "20260224_first_steps"
    question: "Was she walking toward someone?"
    status: "asked"
    created_at: "2026-02-24T15:30:00"
```

---

#### `config.yaml` — Secrets & Settings (Read-Only Mount)
```yaml
llm:
  base_url: "https://routellm.abacus.ai/v1"
  api_key: "YOUR_KEY"
  morning_model: "claude-sonnet-4-6"
  parsing_model: "gpt-4.1-mini"
messaging:
  provider: "twilio"
  twilio:
    account_sid: "..."
    auth_token: "..."
    whatsapp_from: "whatsapp:+1415..."
    whatsapp_to: "whatsapp:+1972..."
google_photos:
  client_id: "..."
  client_secret: "..."
  refresh_token: "..."
face_recognition:
  provider: "aws_rekognition"
  aws:
    access_key: "..."
    secret_key: "..."
    region: "us-east-1"
    collection_id: "elephant_faces"
geocoding:
  provider: "google"
  api_key: "..."
schedule:
  morning_digest: "07:00"
  evening_checkin: "20:00"
  timezone: "America/Chicago"
```

---

### 5. Media Ingestion Pipeline

Triggered on a schedule or when new files are detected. Deduplicates by `sha256`.

```
New photo/video detected
        │
        ▼
1. Dedup (sha256 vs photo_index/<date>.yaml)
        │
        ▼
2. Extract EXIF metadata
   → taken_at, GPS, camera model
        │
        ▼
3. Reverse geocode GPS
   → "Riverside Park, OR"
        │
        ▼
4. Face detection (AWS Rekognition)
   → bounding boxes + face crops
        │
        ▼
5. Face matching vs known people
   → high confidence → auto-tag person_id
   → low confidence → add to pending_questions.yaml
        │
        ▼
6. Auto-link to events
   → match by date + people overlap
        │
        ▼
7. Append to photo_index/<YYYY>/<MM>/<date>.yaml
        │
        ▼
8. Git commit: "[ingest] 18 photos indexed — 2026-02-24"
```

#### Photo Sources
| Source | Method |
| :--- | :--- |
| Google Photos | Google Photos API (OAuth2) |
| Apple Photos | `osxphotos` library (macOS) or iCloud synced folder |
| Local/Synced Folders | `watchdog` filesystem watcher |

---

### 6. Messaging & Interaction

#### Primary Channel Options
| Platform | Replies | Reactions | Cost | Recommendation |
| :--- | :--- | :--- | :--- | :--- |
| WhatsApp (Twilio) | ✅ | ❌ (text only) | ~$2–5/mo | Best UX |
| Telegram Bot | ✅ | ✅ (emoji) | Free | Best Value |
| iMessage (macOS bridge) | ✅ | ✅ (Tapbacks) | Free | Fragile |

#### Context Resolver
When a message arrives, the system checks:
1. Does it have a `reply_to_id`? → Link directly to that event/digest.
2. Is it within 30 minutes of the morning digest? → Assume it's feedback.
3. Otherwise → Treat as a new anytime log entry.

---

### 7. Daily Flows

#### 🌅 Morning Digest (7:00 AM)
```
1. Query events/**/*.yaml for month-day == today
2. Load context.yaml (family knowledge)
3. Load preferences.yaml (nostalgia weights)
4. Score and rank matching events
5. Find best matching photo from photo_index/ files
6. Build LLM context pack (events + photo metadata + context)
7. LLM (claude-sonnet-4-6) writes warm morning story
8. Send via WhatsApp/Telegram with photo attached
9. Git commit: "[morning] Digest sent — 2026-02-24"
```

#### 🌙 Evening Check-in (8:00 PM)
```
1. Scan photo_index/<today>.yaml for media taken today
2. Identify people and places from today's photos
3. Send smart prompt: "I saw 5 photos of Lily at the park today. Anything to remember?"
4. User replies in free text
5. LLM (gpt-4.1-mini) parses reply → structured YAML event
6. Auto-link today's photos to the new event
7. Write new event file to events/<YYYY>/<MM>/<YYYYMMDD>_<slug>.yaml
8. Git commit: "[evening] Daily log — 2026-02-24"
```

#### ⚡ Anytime Logging
```
1. User texts: "Lily just took her first steps!"
2. Webhook receives message + timestamp (14:15)
3. LLM identifies intent: NEW_EVENT
4. Temporal cross: find media taken within ±15 min
5. LLM parses text → structured YAML event
6. Auto-link found media to event
7. Write new event file to events/<YYYY>/<MM>/<YYYYMMDD>_<slug>.yaml
8. Reply: "Saved! Linked 3 videos and 5 photos. 🐘"
9. Git commit: "[event] Lily's first steps — 2026-02-24 14:15"
```

---

### 8. Proactive Clarification

The system sends occasional questions to enrich its knowledge. These are managed via `pending_questions.yaml` to avoid being annoying.

#### A. Immediate Follow-up (Journalist Mode)
After logging a thin event:
- **Elephant:** "That's amazing! Was she walking toward someone? I see you were at Riverside Park — was this her first time walking on grass?"

#### B. Context Gap Filling (Historian Mode)
When a new face appears repeatedly:
- **Elephant:** "Hey, I've noticed a new face in 10 photos this week. They were at your house and the park. Who is this?"
- **User:** "That's my cousin Rafael visiting from Brazil."
- **System:** Updates `context.yaml` and `people.yaml` automatically.

---

### 9. Feedback & Personalization Loop

When you reply "nice," "great," "boring," or "not nice" to a morning digest:

```
1. Context Resolver links reply to the morning digest event
2. LLM classifies sentiment: Positive / Neutral / Negative
3. System identifies features of that event:
   - type (milestone vs. mundane)
   - people count
   - photo quality
   - story length
4. Update preferences.yaml weights accordingly
5. Git commit: "[feedback] Positive — 20260224_first_steps"
```

Over time, the morning digest becomes increasingly personalized to what makes you smile.

---

### 10. Error Handling & Resilience

All pipelines (ingestion, digest, webhook) must handle external API failures gracefully.

#### Retry Strategy
- **Transient failures** (HTTP 429, 500, 503, timeouts): Retry up to 3 times with exponential backoff (1s, 4s, 16s).
- **Auth failures** (HTTP 401, 403): Log error, alert via messaging, do not retry.

#### Graceful Degradation
| Failure | Behavior |
| :--- | :--- |
| Rekognition down | Ingest photos without face detection; queue for retry |
| LLM API down | Skip morning digest; retry at next scheduled slot |
| Twilio/Telegram down | Queue outbound messages; deliver on recovery |
| Google Photos API down | Skip sync cycle; retry on next schedule |
| Geocoding API down | Store raw GPS; reverse-geocode in next pass |

#### Pending Retries
Failed operations are written to `pending_retries.yaml` with the original payload and a retry counter. A background sweep retries them periodically.

#### Health Check
The HTTP server on port 8080 exposes a `/health` endpoint. Docker uses it as a `healthcheck` so the container restarts automatically if the service becomes unresponsive.

---

### 11. Security

#### Webhook Validation
- **Twilio:** Validate the `X-Twilio-Signature` header against your auth token before processing any incoming message.
- **Telegram:** Verify requests originate from Telegram by checking the bot token secret in the webhook URL path.

#### API Key Management
- All secrets live in `config.yaml`, mounted read-only from the host.
- Never log or commit API keys. The `.gitignore` excludes the config directory.

#### Media Privacy
- Photos and videos are stored locally and never uploaded to third-party services beyond what's required (face detection crops sent to Rekognition).
- Face detection can be disabled in `config.yaml` for full local-only operation.

---

### 12. Audit, Logs & CLI Tooling

#### Git Commit Convention
| Trigger | Commit Message |
| :--- | :--- |
| New event logged | `[event] Lily's first steps — 2026-02-24 14:15` |
| Evening check-in | `[evening] Daily log — 2026-02-24` |
| Morning digest sent | `[morning] Digest sent — 2026-02-24` |
| Photos ingested | `[ingest] 18 photos indexed — 2026-02-24` |
| Face named | `[people] Cluster c_009 → Lily` |
| Feedback received | `[feedback] Positive — 20260224_first_steps` |
| Context updated | `[context] Added Rafael as cousin` |

#### Log Files
- **`logs/app.log`** — Technical pipeline logs for debugging.
- **`logs/interactions.log`** — Human-readable record of every message in/out.

#### `yq` CLI Examples
```bash
# Find all events on Feb 24 across all years
yq 'select(.date | test("-02-24"))' events/*/02/*.yaml

# List all milestones involving Lily (search all events)
yq 'select(.type == "milestone" and .people[] == "Lily") | .title' events/**/*.yaml

# List all events from February 2026
yq '.id + " — " + .title' events/2026/02/*.yaml

# Find photos taken on a specific day
yq '.[] | .photo_id' photo_index/2026/02/2026-02-24.yaml

# Find all photos with a specific person
yq '.[] | select(.people_detected[] == "daughter") | .photo_id' photo_index/**/*.yaml
```

---

### 13. Cloud APIs Used

| Purpose | Service | Free Tier |
| :--- | :--- | :--- |
| LLM (stories) | RouteLLM (`claude-sonnet-4-6`) | Pay per token |
| LLM (parsing) | RouteLLM (`gpt-4.1-mini`) | Pay per token |
| Face Recognition | AWS Rekognition | 5,000 images/mo free |
| Reverse Geocoding | Google Maps Geocoding API | 28,500 calls/mo free |
| Photo Source | Google Photos API | Free (read-only) |
| Messaging | Twilio (WhatsApp) or Telegram | Telegram is free |

---

### 14. Monthly Cost Estimate

| Category | Service | Cost |
| :--- | :--- | :--- |
| Infrastructure | Self-hosted Docker | $0.00 |
| LLM | RouteLLM API | $1.50 – $3.00 |
| Face Recognition | AWS Rekognition | $1.00 – $2.00 |
| Messaging | Twilio WhatsApp | $2.00 – $5.00 |
| | *Telegram (alternative)* | *$0.00* |
| Storage Backup | S3 / GCS | $0.50 – $2.00 |
| Geocoding | Google Maps | $0.00 |
| **TOTAL (WhatsApp)** | | **$5.00 – $12.00/mo** |
| **TOTAL (Telegram)** | | **$3.00 – $7.00/mo** |

---

### 15. Implementation Phases

| Phase | Name | What Gets Built |
| :--- | :--- | :--- |
| **1** | The Skeleton | Docker setup, YAML schemas, Git auto-commit, `yq` integration, `config.yaml` loading |
| **2** | The Bridge | Twilio/Telegram webhook, RouteLLM integration, basic text-only logging and morning digest |
| **3** | The Eye | Photo/video ingestion pipeline, EXIF extraction, reverse geocoding, photo-event linking |
| **4** | The Face | AWS Rekognition integration, face clustering, face review UI, people auto-tagging |
| **5** | The Crossing | Temporal media crossing (anytime log), evening check-in photo awareness, "On This Day" photo matcher |
| **6** | The Brain | Proactive clarification agent, feedback loop, `preferences.yaml` learning, context enrichment |
