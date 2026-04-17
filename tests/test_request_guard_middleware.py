"""Request guard middleware (B1 length/rate, B8 quotas) tests."""

from fastapi import FastAPI
from fastapi.testclient import TestClient

from agentic_claims.core.config import Settings
from agentic_claims.web.middleware.requestGuard import RequestGuardMiddleware


def _buildApp(settings: Settings) -> FastAPI:
    app = FastAPI()
    app.add_middleware(RequestGuardMiddleware, settings=settings)

    @app.post("/echo")
    async def echo(payload: dict) -> dict:
        return payload

    return app


def _settingsFromOverride(**overrides) -> Settings:
    """Build a Settings object with Spec-A defaults and optional overrides.

    We cannot call Settings(_env_file=None) in isolation because many
    mandatory non-Spec-A fields have no defaults. The test suite's
    conftest.py exposes a `testSettings` fixture — we reuse that path by
    constructing via model_copy.
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
        return Settings(_env_file=None).model_copy(update=overrides)


def testAcceptsShortMessage() -> None:
    app = _buildApp(_settingsFromOverride())
    client = TestClient(app)
    resp = client.post("/echo", json={"message": "hi"})
    assert resp.status_code == 200


def testRejectsOversizedMessage() -> None:
    app = _buildApp(_settingsFromOverride(max_message_chars=10))
    client = TestClient(app)
    resp = client.post("/echo", json={"message": "x" * 50})
    assert resp.status_code == 413


def testRejectsOversizedJustification() -> None:
    app = _buildApp(_settingsFromOverride(max_justification_chars=5))
    client = TestClient(app)
    resp = client.post("/echo", json={"justification": "toolong"})
    assert resp.status_code == 413


def testRejectsControlChars() -> None:
    app = _buildApp(_settingsFromOverride())
    client = TestClient(app)
    resp = client.post("/echo", json={"message": "hi\x07world"})
    assert resp.status_code == 400


def testRateLimitsBurst() -> None:
    app = _buildApp(_settingsFromOverride(rate_limit_messages_per_min=3))
    client = TestClient(app)
    codes = [client.post("/echo", json={"message": "i"}).status_code for _ in range(5)]
    assert codes.count(429) >= 2
