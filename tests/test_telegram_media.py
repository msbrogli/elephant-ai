"""Tests for Telegram media extraction and download helpers."""

from __future__ import annotations

import os
from unittest.mock import AsyncMock, MagicMock

import pytest

from elephant.telegram_media import download_telegram_file, extract_text_and_files


class TestExtractTextAndFiles:
    def test_text_only(self):
        msg = {"text": "Hello world"}
        text, files = extract_text_and_files(msg)
        assert text == "Hello world"
        assert files == []

    def test_caption_fallback(self):
        msg = {"caption": "Look at this!"}
        text, files = extract_text_and_files(msg)
        assert text == "Look at this!"
        assert files == []

    def test_text_preferred_over_caption(self):
        msg = {"text": "Real text", "caption": "Caption text"}
        text, files = extract_text_and_files(msg)
        assert text == "Real text"

    def test_photo_picks_largest(self):
        msg = {
            "caption": "My photo",
            "photo": [
                {"file_id": "small", "width": 90, "height": 90},
                {"file_id": "medium", "width": 320, "height": 320},
                {"file_id": "large", "width": 800, "height": 800},
            ],
        }
        text, files = extract_text_and_files(msg)
        assert text == "My photo"
        assert len(files) == 1
        assert files[0] == {"file_id": "large", "media_type": "photo"}

    def test_document(self):
        msg = {
            "caption": "My doc",
            "document": {"file_id": "doc123", "file_name": "report.pdf"},
        }
        text, files = extract_text_and_files(msg)
        assert text == "My doc"
        assert len(files) == 1
        assert files[0] == {"file_id": "doc123", "media_type": "document"}

    def test_video(self):
        msg = {
            "caption": "My video",
            "video": {"file_id": "vid456", "duration": 30},
        }
        text, files = extract_text_and_files(msg)
        assert text == "My video"
        assert len(files) == 1
        assert files[0] == {"file_id": "vid456", "media_type": "video"}

    def test_photo_without_text(self):
        msg = {
            "photo": [
                {"file_id": "small", "width": 90, "height": 90},
                {"file_id": "big", "width": 1280, "height": 960},
            ],
        }
        text, files = extract_text_and_files(msg)
        assert text == ""
        assert len(files) == 1
        assert files[0]["file_id"] == "big"

    def test_empty_message(self):
        text, files = extract_text_and_files({})
        assert text == ""
        assert files == []

    def test_multiple_media_types(self):
        msg = {
            "caption": "Mixed media",
            "photo": [{"file_id": "ph1", "width": 100, "height": 100}],
            "document": {"file_id": "doc1"},
            "video": {"file_id": "vid1"},
        }
        text, files = extract_text_and_files(msg)
        assert text == "Mixed media"
        assert len(files) == 3
        types = {f["media_type"] for f in files}
        assert types == {"photo", "document", "video"}


class TestDownloadTelegramFile:
    async def test_download_success(self, tmp_path):
        file_content = b"fake image data"

        # Mock getFile response
        get_file_resp = AsyncMock()
        get_file_resp.json = AsyncMock(return_value={
            "ok": True,
            "result": {"file_path": "photos/file_42.jpg"},
        })

        # Mock file download response
        download_resp = AsyncMock()
        download_resp.raise_for_status = MagicMock()

        async def iter_chunked(size):
            yield file_content

        download_resp.content = MagicMock()
        download_resp.content.iter_chunked = iter_chunked

        call_count = 0

        def mock_get(url, **kwargs):
            nonlocal call_count
            call_count += 1
            cm = AsyncMock()
            if call_count == 1:
                cm.__aenter__ = AsyncMock(return_value=get_file_resp)
            else:
                cm.__aenter__ = AsyncMock(return_value=download_resp)
            cm.__aexit__ = AsyncMock(return_value=False)
            return cm

        session = MagicMock()
        session.get = mock_get

        dest = str(tmp_path / "media")
        result = await download_telegram_file(session, "123:ABC", "file_42", dest)

        assert result == os.path.join(dest, "file_42.jpg")
        assert os.path.exists(result)
        with open(result, "rb") as f:
            assert f.read() == file_content

    async def test_download_getfile_error(self, tmp_path):
        error_resp = AsyncMock()
        error_resp.json = AsyncMock(return_value={
            "ok": False,
            "description": "file not found",
        })

        def mock_get(url, **kwargs):
            cm = AsyncMock()
            cm.__aenter__ = AsyncMock(return_value=error_resp)
            cm.__aexit__ = AsyncMock(return_value=False)
            return cm

        session = MagicMock()
        session.get = mock_get

        with pytest.raises(RuntimeError, match="getFile failed"):
            await download_telegram_file(session, "123:ABC", "bad_id", str(tmp_path))
