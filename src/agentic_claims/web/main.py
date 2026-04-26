"""FastAPI application with lifespan-managed LangGraph singleton."""

import logging
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.middleware.sessions import SessionMiddleware
from starlette.responses import JSONResponse, RedirectResponse
from starlette.staticfiles import StaticFiles

from agentic_claims.core.config import getSettings
from agentic_claims.core.graph import getCompiledGraph
from agentic_claims.core.logging import setupLogging
from agentic_claims.eval_worker.orchestrator import EvalOrchestrator
from agentic_claims.web.middleware.cognitoAuth import CognitoAuthMiddleware
from agentic_claims.web.middleware.publicRateLimit import PublicRateLimitMiddleware
from agentic_claims.web.middleware.requestGuard import RequestGuardMiddleware
from agentic_claims.web.routers.analytics import router as analyticsRouter
from agentic_claims.web.routers.audit import router as auditRouter
from agentic_claims.web.routers.auth import router as authRouter
from agentic_claims.web.routers.chat import router as chatRouter
from agentic_claims.web.routers.dashboard import router as dashboardRouter
from agentic_claims.web.routers.manage import router as manageRouter
from agentic_claims.web.routers.pages import router as pagesRouter
from agentic_claims.web.routers.health import router as healthRouter
from agentic_claims.web.routers.logs import router as logsRouter
from agentic_claims.web.routers.llmasjudge import router as llmasjudgeRouter
from agentic_claims.web.routers.policies import router as policiesRouter
from agentic_claims.web.routers.review import router as reviewRouter

logger = logging.getLogger(__name__)

# Legacy path constants kept for RequestGuardMiddleware reference
_PUBLIC_PATHS = {"/login", "/logout", "/llmasjudge", "/architecture"}
_PUBLIC_PREFIXES = ("/static/", "/llmasjudge/", "/architecture/")


def _findProjectRoot() -> Path:
    """Find the project root containing static/ and templates/ directories.

    Walks up from this file's location. Falls back to /app (Docker workdir)
    then cwd.
    """
    candidate = Path(__file__).resolve().parent
    for _ in range(10):
        candidate = candidate.parent
        if (candidate / "static").is_dir() and (candidate / "templates").is_dir():
            return candidate
    # Docker workdir fallback
    docker = Path("/app")
    if (docker / "static").is_dir():
        return docker
    return Path.cwd()


projectRoot = _findProjectRoot()


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Initialize graph and checkpointer once at startup (singleton pattern)."""
    setupLogging()
    graph, pool = await getCompiledGraph()
    app.state.graph = graph
    app.state.pool = pool
    app.state.settings = settings
    logger.info("LangGraph graph and checkpointer initialized (lifespan singleton)")
    app.state.evalOrchestrator = EvalOrchestrator()
    await app.state.evalOrchestrator.markOrphansInterrupted()
    logger.info("EvalOrchestrator initialised; orphaned runs marked interrupted")
    yield
    await pool.close()
    logger.info("Checkpointer pool closed")


settings = getSettings()

_REMEMBER_ME_MAX_AGE = 604800  # 7 days in seconds
_SESSION_COOKIE = "agentic_session"


class RememberMeMiddleware(BaseHTTPMiddleware):
    """Patch the session cookie Max-Age to 7 days when remember_me is set.

    Runs outermost (added last) so it sees the Set-Cookie header written by
    SessionMiddleware. When the session contains remember_me=True, appends
    Max-Age to the existing Set-Cookie directive for the session cookie.
    """

    async def dispatch(self, request: Request, callNext):
        response = await callNext(request)
        if not request.session.get("remember_me"):
            return response
        # Patch the Set-Cookie header for the session cookie to add Max-Age
        cookieKey = _SESSION_COOKIE.encode()
        maxAgeBytes = f"; Max-Age={_REMEMBER_ME_MAX_AGE}".encode()
        newHeaders: list[tuple[bytes, bytes]] = []
        for name, value in response.raw_headers:
            if name == b"set-cookie" and cookieKey in value and b"Max-Age" not in value:
                value = value + maxAgeBytes
            newHeaders.append((name, value))
        response.raw_headers = newHeaders
        return response



app = FastAPI(title="Cognitive Atelier", lifespan=lifespan)

# CORS — allow React SPA origin (CloudFront / localhost dev)
_allowedOrigins = [
    "https://mmga.mdaie-sutd.fit",
    "http://localhost:5173",   # Vite dev server
    "http://localhost:3000",
]
app.add_middleware(
    CORSMiddleware,
    allow_origins=_allowedOrigins,
    allow_credentials=True,
    allow_methods=["GET", "POST", "PUT", "DELETE", "OPTIONS"],
    allow_headers=["Content-Type", "Authorization", "X-Amz-Date", "X-Api-Key"],
)

# Middleware LIFO order (last added = outermost = runs first on request):
#   CognitoAuthMiddleware — validates Cognito JWT; falls back to session (transition window)
#   RememberMeMiddleware — patches Set-Cookie Max-Age on responses
#   SessionMiddleware (innermost) — signs/reads legacy session cookie
app.add_middleware(
    CognitoAuthMiddleware,
    userPoolId=settings.cognito_user_pool_id,
    region=settings.cognito_region,
    clientId=settings.cognito_client_id,
)
app.add_middleware(
    SessionMiddleware,
    secret_key=settings.session_secret_key,
    session_cookie=_SESSION_COOKIE,
    max_age=None,
    same_site="lax",
    https_only=settings.app_env == "prod",
)
app.add_middleware(RememberMeMiddleware)
app.add_middleware(RequestGuardMiddleware, settings=settings)
app.add_middleware(
    PublicRateLimitMiddleware,
    browsePerMin=60,
    playgroundPerMin=settings.eval_max_playground_calls_per_min,
    runsPerHour=settings.eval_max_runs_per_hour,
)

app.mount("/static", StaticFiles(directory=str(projectRoot / "static")), name="static")
app.mount(
    "/architecture",
    StaticFiles(directory=str(projectRoot / "static" / "architecture"), html=True),
    name="architecture",
)

app.include_router(authRouter)
app.include_router(chatRouter)
app.include_router(auditRouter)
app.include_router(dashboardRouter)
app.include_router(reviewRouter)
app.include_router(manageRouter)
app.include_router(analyticsRouter)
app.include_router(healthRouter)
app.include_router(logsRouter)
app.include_router(policiesRouter)
app.include_router(pagesRouter)
app.include_router(llmasjudgeRouter)
