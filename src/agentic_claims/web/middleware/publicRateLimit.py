"""Public rate-limit middleware scoped to /llmasjudge/*.

Three separate sliding windows per client IP:
  - Browse (GET /llmasjudge*)                    -- default 60/min
  - Playground (POST /llmasjudge/playground)     -- default 5/min
  - Run (POST /llmasjudge/run)                   -- default 1/hour

Pure ASGI middleware. Matches the pattern used by RequestGuardMiddleware
(Spec A) — no BaseHTTPMiddleware, no _receive monkey-patch.
"""

from __future__ import annotations

import time
from collections import defaultdict, deque

from starlette.types import ASGIApp, Receive, Scope, Send


async def _sendPlain(send: Send, status: int, body: str) -> None:
    encoded = body.encode()
    await send({
        "type": "http.response.start",
        "status": status,
        "headers": [
            (b"content-type", b"text/plain; charset=utf-8"),
            (b"content-length", str(len(encoded)).encode()),
        ],
    })
    await send({"type": "http.response.body", "body": encoded, "more_body": False})


class PublicRateLimitMiddleware:
    def __init__(
        self,
        app: ASGIApp,
        *,
        browsePerMin: int = 60,
        playgroundPerMin: int = 5,
        runsPerHour: int = 1,
    ) -> None:
        self.app = app
        self._browsePerMin = int(browsePerMin)
        self._playgroundPerMin = int(playgroundPerMin)
        self._runsPerHour = int(runsPerHour)
        self._browseHits: dict[str, deque[float]] = defaultdict(deque)
        self._playgroundHits: dict[str, deque[float]] = defaultdict(deque)
        self._runHits: dict[str, deque[float]] = defaultdict(deque)

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        if scope["type"] != "http":
            await self.app(scope, receive, send)
            return

        path: str = scope.get("path", "")
        if not path.startswith("/llmasjudge"):
            await self.app(scope, receive, send)
            return

        client = scope.get("client") or (None, None)
        ip = client[0] if client and client[0] else "anon"
        method: str = scope.get("method", "GET")
        now = time.time()

        def _prune(window: deque[float], seconds: int) -> None:
            while window and now - window[0] > seconds:
                window.popleft()

        if method == "POST" and path == "/llmasjudge/run":
            window = self._runHits[ip]
            _prune(window, 3600)
            limit = self._runsPerHour
        elif method == "POST" and path == "/llmasjudge/playground":
            window = self._playgroundHits[ip]
            _prune(window, 60)
            limit = self._playgroundPerMin
        else:
            window = self._browseHits[ip]
            _prune(window, 60)
            limit = self._browsePerMin

        if len(window) >= limit:
            await _sendPlain(send, 429, f"rate limit exceeded for {path}")
            return
        window.append(now)
        await self.app(scope, receive, send)
