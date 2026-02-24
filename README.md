# My Little Elephant

A private, self-hosted, AI-powered family memory assistant. It captures life events, learns your
preferences through feedback, and delivers warm nostalgic daily digests via WhatsApp or Telegram.

## What It Does

- **Morning digest** -- surfaces "on this day" memories from previous years, ranked by learned preferences
- **Evening check-in** -- sends a friendly prompt asking what happened today
- **Anytime logging** -- receives messages at any time, parses them into structured events via LLM
- **Feedback loop** -- classifies your reactions to digests (positive/negative) and adjusts nostalgia weights
- **Clarification questions** -- detects thin events and asks follow-up questions to enrich memories
- **Context learning** -- extracts family info from messages and updates its knowledge base

## Supported LLMs

My Little Elephant talks to LLMs through any **OpenAI-compatible** API endpoint. You configure
a single `base_url` + `api_key` in `config.yaml` and pick two models -- one for writing stories
(morning digest) and one for fast parsing (event extraction, intent classification):

```yaml
llm:
  base_url: "https://routellm.abacus.ai/v1"   # any OpenAI-compatible endpoint
  api_key: "YOUR_KEY"
  morning_model: "claude-sonnet-4-6"            # creative writing
  parsing_model: "gpt-4.1-mini"                 # fast structured extraction
```

### Tested providers

| Provider | `base_url` | Notes |
|---|---|---|
| **Anthropic** (via RouteLLM / proxy) | `https://routellm.abacus.ai/v1` | Default. Recommended `claude-sonnet-4-6` for stories. |
| **Anthropic** (direct) | `https://api.anthropic.com/v1` | Requires an Anthropic API key. |
| **OpenAI** | `https://api.openai.com/v1` | Use `gpt-4o` / `gpt-4.1-mini` for both slots. |
| **OpenRouter** | `https://openrouter.ai/api/v1` | Mix-and-match models from multiple providers. |
| **Ollama** (local) | `http://localhost:11434/v1` | Free, fully offline. Try `llama3.1` or `mistral`. |
| **vLLM / LiteLLM** | Your self-hosted URL | Any local inference server with an OpenAI-compatible API. |

You can mix providers by running two instances behind a proxy, or use a routing service
like RouteLLM or OpenRouter that exposes multiple models under one endpoint.

### Choosing models

| Slot | Purpose | Recommended | Budget alternative |
|---|---|---|---|
| `morning_model` | Writing warm, narrative morning digests | `claude-sonnet-4-6` | `gpt-4o-mini`, `llama3.1:70b` |
| `parsing_model` | Structured extraction (events, intents) | `gpt-4.1-mini` | `gpt-4.1-nano`, `mistral` |

The `morning_model` benefits from a larger, more creative model. The `parsing_model` handles
structured YAML output and can be a smaller, cheaper model without quality loss.

## Messaging Providers

Messages are received via webhooks and sent via API. Configure one provider:

### Twilio (WhatsApp)

```yaml
messaging:
  provider: twilio
  twilio:
    account_sid: "ACxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx"
    auth_token: "your_auth_token"
    whatsapp_from: "whatsapp:+14155238886"
    whatsapp_to: "whatsapp:+19725551234"
```

Webhook URL: `https://your-domain/webhook/twilio`

### Telegram

```yaml
messaging:
  provider: telegram
  telegram:
    bot_token: "123456:ABC-DEF1234ghIkl-zyx57W2v1u123ew11"
    chat_id: "123456789"
    webhook_secret: "a-random-secret-string"
```

Webhook URL: `https://your-domain/webhook/telegram/{webhook_secret}`

Set the webhook with:
```bash
curl "https://api.telegram.org/bot{BOT_TOKEN}/setWebhook?url=https://your-domain/webhook/telegram/{webhook_secret}"
```

## Prerequisites

- Python 3.12+
- [uv](https://docs.astral.sh/uv/) (recommended) or pip
- Git
- Docker and Docker Compose (for containerized deployment)

## Local Development

### Install dependencies

```bash
uv sync --all-extras
```

### Run tests

```bash
uv run pytest
```

With verbose output:

```bash
uv run pytest -v
```

### Linting and type checking

```bash
uv run ruff check src/ tests/
uv run ruff format --check src/ tests/
uv run mypy src/elephant/
```

Auto-fix lint issues:

```bash
uv run ruff check --fix src/ tests/
uv run ruff format src/ tests/
```

### Run locally (outside Docker)

Create a config file:

```yaml
# config.yaml
llm:
  base_url: "https://routellm.abacus.ai/v1"
  api_key: "YOUR_KEY"
schedule:
  morning_digest: "07:00"
  evening_checkin: "20:00"
  timezone: "America/Chicago"
messaging:
  provider: telegram
  telegram:
    bot_token: "YOUR_BOT_TOKEN"
    chat_id: "YOUR_CHAT_ID"
    webhook_secret: "YOUR_SECRET"
```

Create a data directory and start the service:

```bash
mkdir -p /tmp/elephant-data
DATA_DIR=/tmp/elephant-data PORT=8080 uv run python -m elephant.main config.yaml
```

Or using environment variables for everything:

```bash
export CONFIG_PATH=./config.yaml
export DATA_DIR=/tmp/elephant-data
export PORT=8080
uv run python -m elephant.main
```

Verify the health endpoint:

```bash
curl http://localhost:8080/health
# {"status": "ok", "service": "my-little-elephant"}
```

Test a webhook (Telegram example):

```bash
curl -X POST http://localhost:8080/webhook/telegram/YOUR_SECRET \
  -H "Content-Type: application/json" \
  -d '{"message":{"message_id":1,"chat":{"id":123},"text":"Lily took her first steps today!","date":1709251200}}'
```

## Docker

### Build

```bash
docker compose build
```

### Run

Before starting, create the host directories and config file:

```bash
sudo mkdir -p /data/elephant /media/library /config
```

Write your config to `/config/config.yaml` (see the example above), then:

```bash
docker compose up -d
```

Verify:

```bash
curl http://localhost:8080/health
docker compose logs -f
```

### Stop

```bash
docker compose down
```

### Mount points

| Host Path | Container Path | Purpose |
|---|---|---|
| `/data/elephant` | `/app/data` | YAML files, Git repo, logs |
| `/media/library` | `/app/media` | Photo/video blobs (not in Git) |
| `/config` | `/app/config` | `config.yaml` (read-only mount) |

Edit `docker-compose.yml` to change these paths for your system.

## Architecture

### Message Flow

```
Incoming message (Twilio/Telegram webhook)
  -> Context Resolver (determine intent)
  -> Route:
     NEW_EVENT       -> Event Parser (LLM) -> DataStore -> Git commit
     DIGEST_FEEDBACK -> Sentiment classifier -> Adjust preference weights
     ANSWER_QUESTION -> Enrich original event via LLM
     CONTEXT_UPDATE  -> Update context.yaml / people.yaml
```

### Scheduled Tasks

| Schedule | Flow | Description |
|---|---|---|
| Daily (configurable) | Morning Digest | Query "on this day" events, score, LLM story, send |
| Daily (configurable) | Evening Check-in | LLM-generated prompt asking about today |
| Every 15 minutes | Question Manager | Send pending clarification questions |

### Feedback Loop

When the user reacts to a digest (reply or message within 30 min), the system:
1. Classifies sentiment (positive / neutral / negative) via LLM
2. Extracts features from the digest events (type, people count, location)
3. Adjusts matching nostalgia weights by +/-0.1, clamped to [0.1, 3.0]
4. Commits the updated preferences to Git

## Project Structure

```
src/elephant/
  __init__.py              # Package marker, version
  main.py                  # Entry point: wire all components, start server
  config.py                # Load config.yaml into frozen dataclasses
  git_ops.py               # Git init, auto-commit with conventional messages
  health.py                # aiohttp server with /health + webhook routes
  atomic.py                # Atomic file write (write-to-temp, fsync, rename)
  scheduler.py             # Pure asyncio daily/periodic scheduler
  event_parser.py          # LLM parses free text -> Event model
  event_scorer.py          # Score events by nostalgia weights for ranking
  context_resolver.py      # Determine message intent from metadata + timing

  data/
    models.py              # Pydantic models (Event, DigestState, Person, etc.)
    schemas.py             # YAML schema definitions as constants
    store.py               # DataStore: YAML I/O, event querying, schema deployment

  llm/
    client.py              # OpenAI-compatible HTTP client with retry
    prompts.py             # All prompt templates as functions -> message arrays

  messaging/
    base.py                # MessagingClient protocol, SendResult, IncomingMessage
    twilio.py              # TwilioClient (send via Twilio REST API)
    telegram.py            # TelegramClient (send via Telegram Bot API)

  webhooks/
    twilio.py              # POST /webhook/twilio + HMAC-SHA1 validation
    telegram.py            # POST /webhook/telegram/{secret}

  flows/
    morning_digest.py      # Query events -> score -> LLM story -> send -> git commit
    evening_checkin.py      # Generate prompt -> send
    anytime_log.py         # Resolve intent -> route to event/feedback/answer/context

  brain/
    feedback.py            # Classify sentiment -> adjust preference weights
    clarification.py       # Generate follow-up questions for thin events
    context_enrichment.py  # Parse user answers -> update context.yaml / people.yaml
    question_manager.py    # Periodic: send pending questions via messaging

tests/
  conftest.py              # Shared fixtures (configs, stores, mocks)
  test_atomic.py           # Atomic file writes
  test_config.py           # Config loading (including Telegram)
  test_models.py           # Pydantic model validation
  test_store.py            # DataStore YAML I/O
  test_git_ops.py          # Git operations
  test_health.py           # Health endpoint
  test_main.py             # Integration tests
  test_llm_client.py       # Retry logic, error classes
  test_prompts.py          # Prompt template validation
  test_messaging_twilio.py # Mocked Twilio sends
  test_messaging_telegram.py # Mocked Telegram sends
  test_webhook_twilio.py   # HMAC validation, message parsing
  test_webhook_telegram.py # Secret path validation
  test_context_resolver.py # All intent branches
  test_event_parser.py     # Mocked LLM -> Event
  test_event_scorer.py     # Deterministic scoring
  test_scheduler.py        # Scheduler start/stop/periodic
  test_feedback.py         # Sentiment + weight math
  test_clarification.py    # Question gen, answer processing, rate limiting
  test_context_enrichment.py # Context/people updates
  test_question_manager.py # Pending question sending
  test_morning_digest.py   # Full digest flow
  test_evening_checkin.py  # Full checkin flow
  test_anytime_log.py      # Intent routing, all branches
```

## Data Directory Layout

On first run, the service creates this structure under the data directory:

```
events/
  _schema.yaml
  2025/02/20250224_first_steps.yaml
photo_index/
  _schema.yaml
video_index/
  _schema.yaml
faces/
logs/
  app.log
people.yaml
context.yaml
preferences.yaml
pending_questions.yaml
digest_state.yaml
.git/
.gitignore
```

All data files are human-readable YAML, version-controlled by Git. The service
auto-commits changes using conventional tags like `[event]`, `[morning]`, `[feedback]`,
`[context]`, `[enrichment]`.

## Development with Claude Code

This project is developed using [Claude Code](https://docs.anthropic.com/en/docs/claude-code),
Anthropic's CLI coding assistant. To work on this codebase with Claude Code:

```bash
# Install Claude Code
npm install -g @anthropic-ai/claude-code

# Start a session in the project directory
cd /path/to/elephant
claude
```

Claude Code has full context of the project structure, tests, and conventions.
