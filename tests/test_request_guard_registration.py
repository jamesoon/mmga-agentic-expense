"""Ensure RequestGuardMiddleware is registered on the FastAPI app (guard against regressions)."""

import os
from unittest.mock import AsyncMock, patch

import pytest

from agentic_claims.web.middleware.requestGuard import RequestGuardMiddleware


@pytest.fixture(autouse=True)
def _setTestEnv():
    """Load test environment variables before any app import."""
    test_env_file = "tests/.env.test"
    if os.path.exists(test_env_file):
        with open(test_env_file) as f:
            for line in f:
                line = line.strip()
                if line and not line.startswith("#"):
                    key, _, val = line.partition("=")
                    os.environ.setdefault(key, val)


@pytest.fixture
def mockApp():
    """Import and return the app with mocked lifespan."""
    with patch("agentic_claims.core.graph.getCompiledGraph") as mockGetGraph:
        mockGraph = AsyncMock()
        mockPool = AsyncMock()
        mockGetGraph.return_value = (mockGraph, mockPool)

        from agentic_claims.web.main import app

        return app


def testRequestGuardMiddlewareIsRegisteredOnApp(mockApp) -> None:
    """Verify RequestGuardMiddleware is registered in the app's middleware stack."""
    middlewareClasses = [m.cls for m in mockApp.user_middleware]
    assert RequestGuardMiddleware in middlewareClasses
