"""Public rate limit middleware tests (scoped to /llmasjudge/*)."""

from fastapi import FastAPI
from fastapi.testclient import TestClient

from agentic_claims.web.middleware.publicRateLimit import PublicRateLimitMiddleware


def _buildApp(browsePerMin: int, playgroundPerMin: int, runsPerHour: int) -> FastAPI:
    app = FastAPI()
    app.add_middleware(
        PublicRateLimitMiddleware,
        browsePerMin=browsePerMin,
        playgroundPerMin=playgroundPerMin,
        runsPerHour=runsPerHour,
    )

    @app.get("/llmasjudge")
    async def browse() -> dict:
        return {"ok": True}

    @app.get("/other")
    async def other() -> dict:
        return {"ok": True}

    @app.post("/llmasjudge/playground")
    async def playground() -> dict:
        return {"ok": True}

    @app.post("/llmasjudge/run")
    async def run() -> dict:
        return {"ok": True}

    return app


def testBrowseBelowLimitPasses() -> None:
    app = _buildApp(browsePerMin=5, playgroundPerMin=5, runsPerHour=5)
    client = TestClient(app)
    for _ in range(5):
        assert client.get("/llmasjudge").status_code == 200


def testBrowseAboveLimitThrottles() -> None:
    app = _buildApp(browsePerMin=3, playgroundPerMin=5, runsPerHour=5)
    client = TestClient(app)
    codes = [client.get("/llmasjudge").status_code for _ in range(6)]
    assert codes.count(429) >= 2


def testNonLlmasjudgePathsNotLimited() -> None:
    app = _buildApp(browsePerMin=1, playgroundPerMin=1, runsPerHour=1)
    client = TestClient(app)
    codes = [client.get("/other").status_code for _ in range(10)]
    assert all(c == 200 for c in codes)


def testPlaygroundHasSeparateLimit() -> None:
    app = _buildApp(browsePerMin=100, playgroundPerMin=2, runsPerHour=5)
    client = TestClient(app)
    codes = [client.post("/llmasjudge/playground").status_code for _ in range(5)]
    assert codes.count(429) >= 2


def testRunHasSeparateLimit() -> None:
    app = _buildApp(browsePerMin=100, playgroundPerMin=100, runsPerHour=1)
    client = TestClient(app)
    codes = [client.post("/llmasjudge/run").status_code for _ in range(3)]
    assert codes.count(429) >= 1
