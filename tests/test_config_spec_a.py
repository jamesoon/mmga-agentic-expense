"""Validate Spec-A config knobs exist with correct defaults."""

import pytest

from agentic_claims.core.config import Settings


def testHardCapPerReceiptDefault(testSettings: Settings) -> None:
    assert testSettings.hard_cap_per_receipt_sgd == 5000.0


def testHardCapPerClaimDefault(testSettings: Settings) -> None:
    assert testSettings.hard_cap_per_claim_sgd == 10000.0


def testHardCapPerEmployeeMonthDefault(testSettings: Settings) -> None:
    assert testSettings.hard_cap_per_employee_per_month_sgd == 20000.0


def testSoftCapMultiplierDefault(testSettings: Settings) -> None:
    assert testSettings.soft_cap_multiplier == 1.5


def testCritiqueEnabledDefault(testSettings: Settings) -> None:
    assert testSettings.compliance_critique_enabled is True


def testCritiqueTemperatureDefault(testSettings: Settings) -> None:
    assert testSettings.compliance_critique_temperature == 0.0


def testRequestGuardLimitsDefault(testSettings: Settings) -> None:
    assert testSettings.max_justification_chars == 500
    assert testSettings.max_message_chars == 2000
    assert testSettings.rate_limit_messages_per_min == 20
    assert testSettings.quota_submissions_per_day == 20
    assert testSettings.quota_retries_per_hour == 5


def testSpecADefaultsAreCodeLevel() -> None:
    """Guard: Python-level defaults match the spec independent of .env files.

    pydantic-settings requires the mandatory non-Spec-A env vars to be present
    for Settings() construction, so we supply placeholders for those fields
    and rely on defaults for every Spec-A field.
    """
    import os
    from unittest.mock import patch

    requiredPlaceholders = {
        "POSTGRES_HOST": "h", "POSTGRES_PORT": "5432", "POSTGRES_DB": "d",
        "POSTGRES_USER": "u", "POSTGRES_PASSWORD": "p",
        "CHAINLIT_HOST": "0.0.0.0", "CHAINLIT_PORT": "8000",
        "APP_ENV": "test",
        "OPENROUTER_API_KEY": "k", "OPENROUTER_MODEL_LLM": "m",
        "OPENROUTER_MODEL_VLM": "m", "OPENROUTER_FALLBACK_MODEL_LLM": "m",
        "OPENROUTER_FALLBACK_MODEL_VLM": "m", "OPENROUTER_BASE_URL": "http://x",
        "OPENROUTER_MAX_RETRIES": "3", "OPENROUTER_RETRY_DELAY": "1.0",
        "OPENROUTER_VLM_MAX_TOKENS": "512", "OPENROUTER_LLM_MAX_TOKENS": "512",
        "OPENROUTER_LLM_TEMPERATURE": "0.3", "OPENROUTER_TIMEOUT": "30",
        "QDRANT_HOST": "h", "QDRANT_PORT": "6333",
        "RAG_MCP_URL": "http://x", "DB_MCP_URL": "http://x",
        "CURRENCY_MCP_URL": "http://x", "EMAIL_MCP_URL": "http://x",
        "IMAGE_QUALITY_THRESHOLD": "100.0", "IMAGE_MIN_WIDTH": "100",
        "IMAGE_MIN_HEIGHT": "100", "VLM_CONFIDENCE_THRESHOLD": "0.5",
        "SESSION_SECRET_KEY": "k", "LOG_LEVEL": "INFO", "LOG_FILE_PATH": "",
    }
    with patch.dict(os.environ, requiredPlaceholders, clear=True):
        s = Settings(_env_file=None)
    assert s.hard_cap_per_receipt_sgd == 5000.0
    assert s.hard_cap_per_claim_sgd == 10000.0
    assert s.hard_cap_per_employee_per_month_sgd == 20000.0
    assert s.soft_cap_multiplier == 1.5
    assert s.compliance_critique_enabled is True
    assert s.compliance_critique_model is None
    assert s.compliance_critique_temperature == 0.0
    assert s.max_justification_chars == 500
    assert s.max_message_chars == 2000
    assert s.rate_limit_messages_per_min == 20
    assert s.quota_submissions_per_day == 20
    assert s.quota_retries_per_hour == 5
