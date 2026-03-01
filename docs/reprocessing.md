# Reprocessing Messages

Elephant records every incoming message in its raw form to `raw_messages.yaml` before any processing happens. This makes it possible to replay the full message history against a fresh database whenever the processing logic changes — producing an updated set of events, chat history, and other derived data without losing anything.

## How it works

### Raw message capture

Every call to `AnytimeLogFlow.handle_message()` immediately persists the incoming message to `raw_messages.yaml` **before** intent resolution or any other processing. The stored fields are:

| Field         | Description                              |
|---------------|------------------------------------------|
| `text`        | Message body                             |
| `sender`      | Sender identifier                        |
| `message_id`  | Unique message ID from the platform      |
| `timestamp`   | When the message was sent                |
| `reply_to_id` | ID of the message being replied to (optional) |
| `attachments`  | List of `{file_path, media_type}` entries |

This means even messages that fail during processing are recorded and can be replayed later.

### Replay process

The `elephant.reprocess` module replays messages through these steps:

1. **Read** `raw_messages.yaml` from the source data directory and sort by timestamp.
2. **Copy** `media/` and `context.yaml` from source to target. Media files are needed because attachment paths reference them. Context is copied because it's hand-authored family data, not derived.
3. **Initialize** a fresh target database (`DataStore.initialize()` + `GitRepo.initialize()`).
4. **Create** an `AnytimeLogFlow` wired to a real LLM client but a `NullMessagingClient` — so messages are processed normally but nothing is sent to Telegram/WhatsApp.
5. **Replay** each message in chronological order through `flow.handle_message()`. Errors on individual messages are logged and skipped without aborting the run.

### What gets rebuilt

The target database ends up with freshly generated:

- Events (from message parsing)
- Chat history (from LLM conversations)
- Pending questions, digest state, etc.
- Git history of all changes

### What is NOT replayed

- Scheduled flows (morning digest, evening check-in) — these are time-triggered, not message-driven.
- Outgoing messages — the `NullMessagingClient` silently discards all sends.

## Running it

```
uv run python -m elephant.reprocess <source_dir> <target_dir> [-c config.yaml]
```

### Arguments

| Argument       | Description |
|----------------|-------------|
| `source_dir`   | Path to the existing data directory containing `raw_messages.yaml` |
| `target_dir`   | Path where the fresh database will be created |
| `-c, --config` | Path to `config.yaml`. Defaults to `$CONFIG_PATH` or `/app/config/config.yaml` |

### Example

```bash
# Replay all messages into a new directory
uv run python -m elephant.reprocess /app/data /app/data-v2 -c /app/config/config.yaml

# Then compare the two databases
diff -r /app/data/events /app/data-v2/events
```

### Requirements

- The source directory must contain `raw_messages.yaml` with at least one message.
- A valid `config.yaml` is required so the reprocessor can connect to the LLM API.
- The LLM API must be reachable — every message is re-processed through the same LLM pipeline.

### Cost considerations

Reprocessing makes real LLM API calls for every message. For a database with hundreds of messages, this will consume API credits proportional to a full re-run. Consider doing a dry run with a small subset first if cost is a concern.
