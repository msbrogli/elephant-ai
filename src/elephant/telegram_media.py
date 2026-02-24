"""Shared Telegram media extraction and download helpers."""

from __future__ import annotations

import logging
import os
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    import aiohttp

logger = logging.getLogger(__name__)

BOT_API = "https://api.telegram.org"


def extract_text_and_files(tg_message: dict[str, Any]) -> tuple[str, list[dict[str, str]]]:
    """Extract text and file references from a Telegram message.

    Returns (text, file_infos) where text falls back to caption when text is empty.
    file_infos is a list of {"file_id": ..., "media_type": "photo"|"video"|"document"}.
    For photos, picks the largest size (last in Telegram's photo array).
    """
    text = tg_message.get("text", "") or tg_message.get("caption", "") or ""
    file_infos: list[dict[str, str]] = []

    # Photos: array of PhotoSize, pick largest (last element)
    photos = tg_message.get("photo")
    if photos:
        largest = photos[-1]
        file_infos.append({"file_id": largest["file_id"], "media_type": "photo"})

    # Document
    document = tg_message.get("document")
    if document:
        file_infos.append({"file_id": document["file_id"], "media_type": "document"})

    # Video
    video = tg_message.get("video")
    if video:
        file_infos.append({"file_id": video["file_id"], "media_type": "video"})

    return text, file_infos


async def download_telegram_file(
    session: aiohttp.ClientSession,
    bot_token: str,
    file_id: str,
    dest_dir: str,
) -> str:
    """Download a file from Telegram by file_id.

    Calls getFile API to get the server file path, then downloads the bytes.
    Returns the local file path.
    """
    # Get file path from Telegram
    url = f"{BOT_API}/bot{bot_token}/getFile"
    async with session.get(url, params={"file_id": file_id}) as resp:
        data = await resp.json()
        if not data.get("ok"):
            raise RuntimeError(f"getFile failed: {data.get('description', 'unknown error')}")
        file_path = data["result"]["file_path"]

    # Derive extension from remote path
    ext = os.path.splitext(file_path)[1] or ".bin"
    local_name = f"{file_id}{ext}"
    local_path = os.path.join(dest_dir, local_name)

    # Download the file
    download_url = f"{BOT_API}/file/bot{bot_token}/{file_path}"
    async with session.get(download_url) as resp:
        resp.raise_for_status()
        os.makedirs(dest_dir, exist_ok=True)
        with open(local_path, "wb") as f:
            async for chunk in resp.content.iter_chunked(8192):
                f.write(chunk)

    logger.info("Downloaded Telegram file %s -> %s", file_id, local_path)
    return local_path
