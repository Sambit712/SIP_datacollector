"""Unit tests for centralized configuration & settings (Phase 0)."""

import os
from pathlib import Path
import pytest
import yaml

from config.settings import Settings, get_settings


def test_settings_default_offline_without_api_key(monkeypatch):
    """Verifies that the application default is offline mode when GROQ_API_KEY is not set."""
    monkeypatch.delenv("GROQ_API_KEY", raising=False)
    monkeypatch.delenv("OFFLINE_MODE", raising=False)
    
    settings = Settings(GROQ_API_KEY=None, OFFLINE_MODE=False)
    assert settings.is_offline is True
    assert settings.LLM_PROVIDER == "groq"
    assert len(settings.GROQ_MODEL) > 0


def test_settings_online_when_api_key_provided(monkeypatch):
    """Verifies that is_offline is False when a valid GROQ_API_KEY is provided."""
    settings = Settings(GROQ_API_KEY="gsk_mock_valid_key_1234567890", OFFLINE_MODE=False)
    assert settings.is_offline is False


def test_settings_explicit_offline_override():
    """Verifies that OFFLINE_MODE=True forces offline mode even with an API key."""
    settings = Settings(GROQ_API_KEY="gsk_mock_valid_key_1234567890", OFFLINE_MODE=True)
    assert settings.is_offline is True


def test_database_path_and_url_resolution():
    """Verifies that SQLite database path and URL are properly formatted."""
    settings = Settings()
    db_path = settings.absolute_db_path
    assert isinstance(db_path, Path)
    assert db_path.name.endswith(".sqlite")
    assert settings.database_url.startswith("sqlite:///")


def test_taxonomy_yaml_integrity():
    """Verifies that config/taxonomy.yaml exists and defines the 13 canonical categories."""
    settings = get_settings()
    taxonomy_file = settings.ROOT_DIR / "config" / "taxonomy.yaml"
    assert taxonomy_file.exists(), "config/taxonomy.yaml must exist"

    with open(taxonomy_file, "r", encoding="utf-8") as f:
        data = yaml.safe_load(f)

    assert "categories" in data
    categories = data["categories"]
    assert len(categories) == 13, f"Expected 13 canonical categories, found {len(categories)}"

    # Check key codes
    category_codes = [c["code"] for c in categories]
    assert "cash_flow_mismatch" in category_codes
    assert "payment_failures" in category_codes
    assert "autopay_mandate" in category_codes
    assert "volatility_anxiety" in category_codes
    assert "unclassified" in category_codes

