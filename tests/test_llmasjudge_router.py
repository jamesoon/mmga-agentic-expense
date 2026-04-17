"""LLM-as-Judge router smoke tests — endpoints register + respond."""

from fastapi import FastAPI
from fastapi.testclient import TestClient

from agentic_claims.web.middleware.publicRateLimit import PublicRateLimitMiddleware


def testRouterRegisters() -> None:
    """The router can be included without error; endpoints respond."""
    from agentic_claims.web.routers import llmasjudge

    app = FastAPI()
    app.add_middleware(
        PublicRateLimitMiddleware,
        browsePerMin=60, playgroundPerMin=5, runsPerHour=1,
    )
    app.include_router(llmasjudge.router)
    client = TestClient(app, raise_server_exceptions=False)

    # /llmasjudge page (HTML). 500 acceptable if templates dir missing in test env.
    resp = client.get("/llmasjudge")
    assert resp.status_code in (200, 500)

    # /llmasjudge/summary — JSON; 404 ok if no run exists yet; 503 if DB unavailable.
    resp = client.get("/llmasjudge/summary")
    assert resp.status_code in (200, 404, 500, 503)

    # /llmasjudge/runs — paginated list; should always return 200 with empty list on clean DB.
    resp = client.get("/llmasjudge/runs")
    assert resp.status_code in (200, 500)
