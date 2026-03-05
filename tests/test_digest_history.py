"""Tests for digest history."""

from __future__ import annotations

from datetime import UTC, datetime

from elephant.data.models import DigestHistoryEntry, DigestHistoryFile
from elephant.data.store import DataStore


class TestDigestHistoryStore:
    def test_read_empty(self, data_dir: str) -> None:
        store = DataStore(data_dir)
        store.initialize()

        history = store.read_digest_history()
        assert history.digests == []

    def test_append_and_read(self, data_dir: str) -> None:
        store = DataStore(data_dir)
        store.initialize()

        entry = DigestHistoryEntry(
            sent_at=datetime(2026, 3, 1, 7, 0, tzinfo=UTC),
            text="Good morning! Here are your memories...",
            memory_ids=["20250301_park_day", "20240301_birthday"],
            message_id="msg_123",
        )
        store.append_digest_history(entry)

        history = store.read_digest_history()
        assert len(history.digests) == 1
        assert history.digests[0].text == "Good morning! Here are your memories..."
        assert history.digests[0].memory_ids == ["20250301_park_day", "20240301_birthday"]
        assert history.digests[0].message_id == "msg_123"

    def test_append_multiple(self, data_dir: str) -> None:
        store = DataStore(data_dir)
        store.initialize()

        for i in range(3):
            entry = DigestHistoryEntry(
                sent_at=datetime(2026, 3, i + 1, 7, 0, tzinfo=UTC),
                text=f"Digest {i}",
                memory_ids=[],
            )
            store.append_digest_history(entry)

        history = store.read_digest_history()
        assert len(history.digests) == 3
        assert history.digests[0].text == "Digest 0"
        assert history.digests[2].text == "Digest 2"

    def test_write_and_read_roundtrip(self, data_dir: str) -> None:
        store = DataStore(data_dir)
        store.initialize()

        history = DigestHistoryFile(digests=[
            DigestHistoryEntry(
                sent_at=datetime(2026, 3, 1, 7, 0, tzinfo=UTC),
                text="Test digest",
                memory_ids=["mem1"],
            ),
        ])
        store.write_digest_history(history)

        read_back = store.read_digest_history()
        assert len(read_back.digests) == 1
        assert read_back.digests[0].text == "Test digest"
