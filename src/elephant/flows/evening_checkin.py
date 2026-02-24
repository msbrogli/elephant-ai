"""Evening check-in flow: generate prompt, send."""

import logging

from elephant.data.store import DataStore
from elephant.llm.client import LLMClient
from elephant.llm.prompts import evening_checkin
from elephant.messaging.base import MessagingClient

logger = logging.getLogger(__name__)


class EveningCheckinFlow:
    """Orchestrates the evening check-in message."""

    def __init__(
        self,
        store: DataStore,
        llm: LLMClient,
        model: str,
        messaging: MessagingClient,
    ) -> None:
        self._store = store
        self._llm = llm
        self._model = model
        self._messaging = messaging

    async def run(self) -> bool:
        """Send an evening check-in message. Returns True if sent."""
        context = self._store.read_context()
        messages = evening_checkin(context)
        response = await self._llm.chat(messages, model=self._model)
        checkin_text = (response.content or "").strip()

        results = await self._messaging.broadcast_text(checkin_text)
        if not results or not any(r.success for r in results):
            errors = ", ".join(r.error or "unknown" for r in results)
            logger.error("Failed to send evening checkin: %s", errors or "no approved chats")
            return False

        logger.info("Evening checkin sent")
        return True
