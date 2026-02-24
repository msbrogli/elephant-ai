"""Tests for config loading."""

import pytest
import yaml

from elephant.config import AppConfig, DatabaseConfig, TelegramConfig, load_config


def _write_config(tmp_path, data: dict) -> str:
    path = str(tmp_path / "config.yaml")
    with open(path, "w") as f:
        yaml.dump(data, f)
    return path


# All configs need a databases section now

MINIMAL_CONFIG = {
    "llm": {
        "base_url": "https://api.example.com/v1",
        "api_key": "test-key",
    },
    "databases": {
        "default": {
            "data_dir": "/tmp/data",
            "auth_secret": "test-secret",
        },
    },
}

FULL_CONFIG = {
    "llm": {
        "base_url": "https://routellm.abacus.ai/v1",
        "api_key": "sk-test",
        "morning_model": "claude-sonnet-4-6",
        "parsing_model": "gpt-4.1-mini",
    },
    "messaging": {
        "provider": "twilio",
        "twilio": {
            "account_sid": "AC123",
            "auth_token": "tok456",
            "whatsapp_from": "whatsapp:+1415000",
            "whatsapp_to": "whatsapp:+1972000",
        },
    },
    "schedule": {
        "morning_digest": "08:00",
        "evening_checkin": "21:00",
        "timezone": "America/New_York",
    },
    "databases": {
        "family": {
            "data_dir": "/app/data/family",
            "auth_secret": "abc-123",
        },
    },
}

TELEGRAM_CONFIG = {
    "llm": {
        "base_url": "https://api.example.com/v1",
        "api_key": "test-key",
    },
    "messaging": {
        "provider": "telegram",
        "telegram": {
            "bot_token": "123:ABC",
            "webhook_secret": "secret123",
            "webhook_url": "https://myhost.ngrok.io",
            "mode": "webhook",
        },
    },
    "databases": {
        "default": {
            "data_dir": "/tmp/data",
            "auth_secret": "456",
        },
    },
}


def test_load_minimal_config(tmp_path):
    path = _write_config(tmp_path, MINIMAL_CONFIG)
    config = load_config(path)
    assert isinstance(config, AppConfig)
    assert config.llm.base_url == "https://api.example.com/v1"
    assert config.llm.api_key == "test-key"
    assert config.schedule.timezone == "America/Chicago"


def test_load_full_config(tmp_path):
    path = _write_config(tmp_path, FULL_CONFIG)
    config = load_config(path)
    assert config.llm.morning_model == "claude-sonnet-4-6"
    assert config.schedule.morning_digest == "08:00"
    assert config.messaging.twilio.account_sid == "AC123"


def test_load_telegram_config(tmp_path):
    path = _write_config(tmp_path, TELEGRAM_CONFIG)
    config = load_config(path)
    assert config.messaging.provider == "telegram"
    assert config.messaging.telegram.bot_token == "123:ABC"
    assert config.messaging.telegram.webhook_secret == "secret123"
    assert config.messaging.telegram.webhook_url == "https://myhost.ngrok.io"
    assert config.databases[0].auth_secret == "456"


def test_telegram_config_defaults():
    tc = TelegramConfig()
    assert tc.bot_token == ""
    assert tc.webhook_secret == ""
    assert tc.webhook_url == ""
    assert tc.mode == "polling"


def test_config_is_frozen(tmp_path):
    path = _write_config(tmp_path, MINIMAL_CONFIG)
    config = load_config(path)
    with pytest.raises(AttributeError):
        config.llm = None  # type: ignore[misc]


def test_config_env_fallback(tmp_path, monkeypatch):
    path = _write_config(tmp_path, MINIMAL_CONFIG)
    monkeypatch.setenv("CONFIG_PATH", path)
    config = load_config()
    assert config.llm.api_key == "test-key"


def test_config_missing_file():
    with pytest.raises(FileNotFoundError):
        load_config("/nonexistent/config.yaml")


def test_config_invalid_yaml(tmp_path):
    path = str(tmp_path / "config.yaml")
    with open(path, "w") as f:
        f.write("just a string")
    with pytest.raises(ValueError, match="YAML mapping"):
        load_config(path)


def test_config_with_both_providers(tmp_path):
    """Config can have both twilio and telegram sections."""
    config_data = {
        "llm": {"base_url": "https://api.example.com/v1", "api_key": "test"},
        "messaging": {
            "provider": "telegram",
            "twilio": {"account_sid": "AC1"},
            "telegram": {"bot_token": "123:ABC"},
        },
        "databases": {
            "default": {"data_dir": "/tmp/d", "auth_secret": "456"},
        },
    }
    path = _write_config(tmp_path, config_data)
    config = load_config(path)
    assert config.messaging.provider == "telegram"
    assert config.messaging.twilio.account_sid == "AC1"
    assert config.messaging.telegram.bot_token == "123:ABC"


def test_missing_databases_section_raises(tmp_path):
    """Config without databases section should raise."""
    config_data = {
        "llm": {"base_url": "https://api.example.com/v1", "api_key": "test"},
    }
    path = _write_config(tmp_path, config_data)
    with pytest.raises(ValueError, match="databases"):
        load_config(path)


# --- Multi-database config tests ---


def test_databases_section_parsed(tmp_path):
    """Databases section creates multiple DatabaseConfig entries."""
    config_data = {
        "llm": {"base_url": "https://api.example.com/v1", "api_key": "test"},
        "databases": {
            "brogli": {
                "data_dir": "/app/data/brogli",
                "auth_secret": "abc-123",
                "schedule": {
                    "morning_digest": "07:00",
                    "evening_checkin": "20:00",
                    "timezone": "America/Chicago",
                },
            },
            "smith": {
                "data_dir": "/app/data/smith",
                "auth_secret": "def-456",
                "schedule": {
                    "morning_digest": "08:30",
                    "evening_checkin": "21:00",
                    "timezone": "America/New_York",
                },
            },
        },
    }
    path = _write_config(tmp_path, config_data)
    config = load_config(path)
    assert len(config.databases) == 2
    names = {db.name for db in config.databases}
    assert names == {"brogli", "smith"}
    brogli = next(db for db in config.databases if db.name == "brogli")
    assert brogli.data_dir == "/app/data/brogli"
    assert brogli.auth_secret == "abc-123"
    assert brogli.schedule.morning_digest == "07:00"
    smith = next(db for db in config.databases if db.name == "smith")
    assert smith.schedule.timezone == "America/New_York"


def test_databases_schedule_fallback(tmp_path):
    """Database without schedule falls back to top-level schedule."""
    config_data = {
        "llm": {"base_url": "https://api.example.com/v1", "api_key": "test"},
        "schedule": {
            "morning_digest": "09:00",
            "evening_checkin": "22:00",
            "timezone": "Europe/London",
        },
        "databases": {
            "familyx": {
                "data_dir": "/data/x",
                "auth_secret": "sec-x",
                # no schedule key -> should use top-level
            },
        },
    }
    path = _write_config(tmp_path, config_data)
    config = load_config(path)
    assert len(config.databases) == 1
    db = config.databases[0]
    assert db.schedule.morning_digest == "09:00"
    assert db.schedule.timezone == "Europe/London"


def test_database_config_is_frozen():
    dc = DatabaseConfig(name="test", data_dir="/tmp", auth_secret="sec")
    with pytest.raises(AttributeError):
        dc.name = "other"  # type: ignore[misc]
