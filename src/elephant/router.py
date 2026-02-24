"""ChatRouter: route Telegram chat_ids to DatabaseInstance objects."""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from elephant.database import DatabaseInstance

logger = logging.getLogger(__name__)


class ChatRouter:
    """In-memory index mapping chat_id → DatabaseInstance."""

    def __init__(self) -> None:
        self._by_chat: dict[str, DatabaseInstance] = {}
        self._by_secret: dict[str, DatabaseInstance] = {}
        self._databases: list[DatabaseInstance] = []

    def register_database(self, db: DatabaseInstance) -> None:
        """Index a database by its approved chats and auth_secret."""
        self._databases.append(db)
        self._by_secret[db.auth_secret] = db
        for chat in db.store.read_authorized_chats().chats:
            self._by_chat[chat.chat_id] = db
        logger.info("Router: registered database %r", db.name)

    def resolve_by_chat(self, chat_id: str) -> DatabaseInstance | None:
        """Look up a database by chat_id."""
        return self._by_chat.get(chat_id)

    def resolve_by_auth_secret(self, secret: str) -> DatabaseInstance | None:
        """Look up a database by auth secret (for /start)."""
        return self._by_secret.get(secret)

    def assign_chat(self, chat_id: str, db: DatabaseInstance) -> None:
        """Add a chat_id → db mapping after approval."""
        self._by_chat[chat_id] = db

    def get_all_databases(self) -> list[DatabaseInstance]:
        """Return all registered databases."""
        return list(self._databases)
