"""Tests for raw message storage and capture."""

import os
from datetime import UTC, datetime
from unittest.mock import AsyncMock, MagicMock

import pytest

from elephant.data.models import RawMessage, RawMessageAttachment
from elephant.data.store import DataStore
from elephant.flows.anytime_log import AnytimeLogFlow
from elephant.git_ops import GitRepo
from elephant.llm.client import LLMResponse
from elephant.messaging.base import Attachment, IncomingMessage


@pytest.fixture
def store(data_dir):
    s = DataStore(data_dir)
    s.initialize()
    return s


def _make_raw_message(
    text: str = "hello",
    sender: str = "12345",
    message_id: str = "msg_1",
    reply_to_id: str | None = None,
    attachments: list[RawMessageAttachment] | None = None,
) -> RawMessage:
    return RawMessage(
        text=text,
        sender=sender,
        message_id=message_id,
        timestamp=datetime.now(UTC),
        reply_to_id=reply_to_id,
        attachments=attachments or [],
    )


class TestRawMessageStorage:
    def test_read_empty(self, store):
        raw = store.read_raw_messages()
        assert raw == []

    def test_append_and_read(self, store):
        msg = _make_raw_message(text="test message")
        store.append_raw_message(msg)

        raw = store.read_raw_messages()
        assert len(raw) == 1
        assert raw[0].text == "test message"
        assert raw[0].sender == "12345"
        assert raw[0].message_id == "msg_1"

    def test_append_preserves_attachments(self, store):
        attachments = [
            RawMessageAttachment(file_path="/media/photo1.jpg", media_type="photo"),
            RawMessageAttachment(file_path="/media/doc.pdf", media_type="document"),
        ]
        msg = _make_raw_message(attachments=attachments)
        store.append_raw_message(msg)

        raw = store.read_raw_messages()
        assert len(raw[0].attachments) == 2
        assert raw[0].attachments[0].file_path == "/media/photo1.jpg"
        assert raw[0].attachments[0].media_type == "photo"
        assert raw[0].attachments[1].file_path == "/media/doc.pdf"
        assert raw[0].attachments[1].media_type == "document"

    def test_append_multiple(self, store):
        store.append_raw_message(_make_raw_message(text="first", message_id="m1"))
        store.append_raw_message(_make_raw_message(text="second", message_id="m2"))
        store.append_raw_message(_make_raw_message(text="third", message_id="m3"))

        raw = store.read_raw_messages()
        assert len(raw) == 3
        assert raw[0].text == "first"
        assert raw[1].text == "second"
        assert raw[2].text == "third"

    def test_roundtrip_with_all_fields(self, store):
        now = datetime.now(UTC)
        msg = RawMessage(
            text="reply message",
            sender="user_42",
            message_id="msg_99",
            timestamp=now,
            reply_to_id="msg_50",
            attachments=[
                RawMessageAttachment(file_path="/media/vid.mp4", media_type="video"),
            ],
        )
        store.append_raw_message(msg)

        raw = store.read_raw_messages()
        loaded = raw[0]
        assert loaded.text == "reply message"
        assert loaded.sender == "user_42"
        assert loaded.message_id == "msg_99"
        assert loaded.reply_to_id == "msg_50"
        assert len(loaded.attachments) == 1
        assert loaded.attachments[0].media_type == "video"

    def test_jsonl_format(self, store):
        """Verify that raw messages are stored as JSONL (one JSON per line)."""
        store.append_raw_message(_make_raw_message(text="line1", message_id="m1"))
        store.append_raw_message(_make_raw_message(text="line2", message_id="m2"))

        path = store._raw_messages_jsonl_path()
        with open(path) as f:
            lines = f.readlines()
        assert len(lines) == 2
        import json

        for line in lines:
            data = json.loads(line)
            assert "text" in data
            assert "message_id" in data

    def test_malformed_lines_skipped(self, store):
        """Malformed JSONL lines are silently skipped."""
        path = store._raw_messages_jsonl_path()
        os.makedirs(os.path.dirname(path), exist_ok=True)
        msg = _make_raw_message(text="good line")
        with open(path, "w") as f:
            f.write(msg.model_dump_json() + "\n")
            f.write("this is not valid json\n")
            f.write("{bad json\n")

        raw = store.read_raw_messages()
        assert len(raw) == 1
        assert raw[0].text == "good line"

    def test_yaml_to_jsonl_migration(self, data_dir):
        """Old raw_messages.yaml is migrated to JSONL on first read."""
        import yaml

        store = DataStore(data_dir)
        store.initialize()

        # Write a raw_messages.yaml manually in old format
        yaml_path = os.path.join(data_dir, "raw_messages.yaml")
        now = datetime.now(UTC)
        old_data = {
            "_schema": {"version": 1},
            "messages": [
                {
                    "text": "migrated message",
                    "sender": "user1",
                    "message_id": "old_1",
                    "timestamp": now.isoformat(),
                    "attachments": [],
                },
            ],
        }
        with open(yaml_path, "w") as f:
            yaml.dump(old_data, f)

        # Read should trigger migration
        raw = store.read_raw_messages()
        assert len(raw) == 1
        assert raw[0].text == "migrated message"

        # YAML file should be renamed to .bak
        assert not os.path.exists(yaml_path)
        assert os.path.exists(yaml_path + ".bak")

        # JSONL file should exist
        assert os.path.exists(store._raw_messages_jsonl_path())


class TestRawMessageCapture:
    @pytest.fixture
    def flow_deps(self, data_dir):
        store = DataStore(data_dir)
        store.initialize()
        llm = AsyncMock()
        llm.chat = AsyncMock(return_value=LLMResponse(
            content="classified", model="m", usage={},
        ))
        llm.chat_with_tools = AsyncMock(return_value=LLMResponse(
            content="OK!", model="m", usage={}, tool_calls=[],
        ))
        git = MagicMock(spec=GitRepo)
        git.auto_commit = MagicMock(return_value="abc123")
        messaging = AsyncMock()
        messaging.send_text = AsyncMock()
        messaging.send_chat_action = AsyncMock()
        flow = AnytimeLogFlow(
            store=store,
            llm=llm,
            parsing_model="test-model",
            messaging=messaging,
            git=git,
        )
        return flow, store

    async def test_message_captured_on_handle(self, flow_deps):
        flow, store = flow_deps
        now = datetime.now(UTC)
        message = IncomingMessage(
            text="Lily took her first steps today!",
            sender="12345",
            message_id="msg_100",
            timestamp=now,
            reply_to_id=None,
            attachments=[
                Attachment(file_path="/media/photo.jpg", media_type="photo"),
            ],
        )

        await flow.handle_message(message)

        raw = store.read_raw_messages()
        assert len(raw) == 1
        captured = raw[0]
        assert captured.text == "Lily took her first steps today!"
        assert captured.sender == "12345"
        assert captured.message_id == "msg_100"
        assert len(captured.attachments) == 1
        assert captured.attachments[0].file_path == "/media/photo.jpg"
        assert captured.attachments[0].media_type == "photo"
