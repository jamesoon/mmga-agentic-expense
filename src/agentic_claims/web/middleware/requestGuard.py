"""Request guard middleware — B1 (length/rate/charset) + B8 (quotas).

Pure ASGI middleware using Starlette's BaseHTTPMiddleware. No ORM writes —
audit entries are written downstream via auditHelper (added in a later task).
Stores userQuotaSnapshot on request.state for later pickup by handlers.
"""

from __future__ import annotations

import json
import time
from collections import defaultdict, deque
from typing import Callable

from fastapi import Request, Response
from starlette.middleware.base import BaseHTTPMiddleware

from agentic_claims.core.config import Settings

_SAFE_CHAR_RANGES = [
    (0x09, 0x09),
    (0x0A, 0x0A),
    (0x0D, 0x0D),
    (0x20, 0x7E),
    (0x00A0, 0x10FFFF),
]


def _isSafeChar(ch: str) -> bool:
    cp = ord(ch)
    return any(lo <= cp <= hi for lo, hi in _SAFE_CHAR_RANGES)


class RequestGuardMiddleware(BaseHTTPMiddleware):
    def __init__(self, app, settings: Settings) -> None:
        super().__init__(app)
        self._settings = settings
        self._sessionHits: dict[str, deque[float]] = defaultdict(deque)

    async def dispatch(self, request: Request, call_next: Callable) -> Response:
        s = self._settings
        sessionKey = request.client.host if request.client else "anon"

        body = await request.body()
        parsed: dict = {}
        if body:
            try:
                parsed = json.loads(body)
            except (ValueError, TypeError):
                parsed = {}

        msg = str(parsed.get("message", ""))
        just = str(parsed.get("justification", ""))

        if len(msg) > s.max_message_chars:
            return Response(f"message exceeds {s.max_message_chars} chars", status_code=413)
        if len(just) > s.max_justification_chars:
            return Response(
                f"justification exceeds {s.max_justification_chars} chars",
                status_code=413,
            )

        for text in (msg, just):
            if any(not _isSafeChar(c) for c in text):
                return Response("request contains control characters", status_code=400)

        now = time.time()
        window = self._sessionHits[sessionKey]
        while window and now - window[0] > 60:
            window.popleft()
        if len(window) >= s.rate_limit_messages_per_min:
            return Response("rate limit exceeded", status_code=429)
        window.append(now)

        request.state.userQuotaSnapshot = {
            "sessionKey": sessionKey,
            "timestamp": now,
            "rateWindowDepth": len(window),
        }

        # Rewind the body so downstream handlers can read it.
        async def _receive():
            return {"type": "http.request", "body": body, "more_body": False}

        request._receive = _receive  # type: ignore[attr-defined]
        return await call_next(request)
