"""Shared fixtures for tests."""

from datetime import date
from unittest.mock import AsyncMock

import pytest
import yaml

from elephant.config import (
    AppConfig,
    DatabaseConfig,
    LLMConfig,
    MessagingConfig,
    ScheduleConfig,
    TelegramConfig,
    TwilioConfig,
)
from elephant.data.models import Event
from elephant.data.store import DataStore
from elephant.llm.client import LLMResponse


@pytest.fixture
def sample_config(tmp_path):
    """Create a minimal config.yaml and return its path."""
    data_dir = str(tmp_path / "data")
    config = {
        "llm": {
            "base_url": "https://api.example.com/v1",
            "api_key": "test-key",
        },
        "schedule": {
            "morning_digest": "07:00",
            "evening_checkin": "20:00",
            "timezone": "America/Chicago",
        },
        "databases": {
            "default": {
                "data_dir": data_dir,
                "auth_secret": "test-secret",
            },
        },
    }
    path = tmp_path / "config.yaml"
    path.write_text(yaml.dump(config))
    return str(path)


@pytest.fixture
def data_dir(tmp_path):
    """Return a temporary data directory path."""
    return str(tmp_path / "data")


@pytest.fixture
def full_config():
    """Create a full AppConfig for testing."""
    return AppConfig(
        llm=LLMConfig(
            base_url="https://api.example.com/v1",
            api_key="test-key",
            morning_model="test-model",
            parsing_model="test-parser",
        ),
        databases=(
            DatabaseConfig(
                name="default",
                data_dir="/tmp/test-data",
                auth_secret="456",
            ),
        ),
        schedule=ScheduleConfig(
            morning_digest="07:00",
            evening_checkin="20:00",
            timezone="America/Chicago",
        ),
        messaging=MessagingConfig(
            provider="telegram",
            twilio=TwilioConfig(
                account_sid="AC123",
                auth_token="tok456",
                whatsapp_from="whatsapp:+1415000",
                whatsapp_to="whatsapp:+1972000",
            ),
            telegram=TelegramConfig(
                bot_token="123:ABC",
                webhook_secret="secret123",
                webhook_url="https://myhost.ngrok.io",
                mode="polling",
            ),
        ),
    )


@pytest.fixture
def store_with_events(data_dir):
    """Create a DataStore with some sample events."""
    store = DataStore(data_dir)
    store.initialize()

    events = [
        Event(
            id="20250224_first_steps",
            date=date(2025, 2, 24),
            title="Lily's first steps",
            type="milestone",
            description="Lily took 4 steps toward Dad in the living room!",
            people=["Lily", "Dad"],
            location="Portland, OR",
            source="WhatsApp",
            nostalgia_score=1.5,
        ),
        Event(
            id="20240224_park_day",
            date=date(2024, 2, 24),
            title="Park day",
            type="daily",
            description="Went to the park",
            people=["Lily"],
            source="WhatsApp",
            nostalgia_score=0.8,
        ),
    ]
    for event in events:
        store.write_event(event)

    return store


@pytest.fixture
def mock_llm_response():
    """Factory for creating mock LLM responses."""

    def _make(content: str, model: str = "test-model") -> LLMResponse:
        return LLMResponse(content=content, model=model, usage={"total_tokens": 100})

    return _make


@pytest.fixture
def mock_llm_client(mock_llm_response):
    """Create a mock LLM client."""
    client = AsyncMock()
    client.chat = AsyncMock(return_value=mock_llm_response("test response"))
    return client


@pytest.fixture
def mock_messaging():
    """Create a mock messaging client."""
    from elephant.messaging.base import SendResult

    client = AsyncMock()
    client.send_text = AsyncMock(
        return_value=SendResult(success=True, message_id="msg_123")
    )
    client.send_text_with_media = AsyncMock(
        return_value=SendResult(success=True, message_id="msg_124")
    )
    client.broadcast_text = AsyncMock(
        return_value=[SendResult(success=True, message_id="msg_125")]
    )
    return client
