"""Request guard middleware — B1 (length/rate/charset) + B8 (quotas).

Pure ASGI middleware. We intentionally do NOT subclass BaseHTTPMiddleware
because it makes body-replay brittle (monkey-patching request._receive
violates the ASGI contract: after the body is consumed, receive() must
return http.disconnect, not another http.request).

This middleware:
  - drains the request body into memory
  - validates length + charset against configured caps
  - rate-limits per-client-host per minute
  - replays the drained body to the downstream app via a new receive()
    callable that emits the original messages and then http.disconnect
"""

from __future__ import annotations

import json
import time
from collections import defaultdict, deque
from typing import Any

from starlette.types import ASGIApp, Message, Receive, Scope, Send

from agentic_claims.core.config import Settings

_SAFE_CHAR_RANGES = [
    (0x09, 0x09),
    (0x0A, 0x0A),
    (0x0D, 0x0D),
    (0x20, 0x7E),
    (0x00A0, 0x10FFFF),
]

_BODY_METHODS = {"POST", "PUT", "PATCH"}

# Paths that are NEVER rate-limited by B1 (static assets, health checks,
# documentation pages). These are cheap / stateless and have no LLM cost.
_NO_RATE_LIMIT_PREFIXES = (
    "/static/",
    "/architecture/",
    "/favicon",
    "/health",
    "/llmasjudge/summary",
    "/llmasjudge/runs",
    "/llmasjudge/analyses",
)


def _isSafeChar(ch: str) -> bool:
    cp = ord(ch)
    return any(lo <= cp <= hi for lo, hi in _SAFE_CHAR_RANGES)


async def _sendPlainResponse(send: Send, statusCode: int, body: str) -> None:
    """Emit an ASGI HTTP response with a plain-text body."""
    await send(
        {
            "type": "http.response.start",
            "status": statusCode,
            "headers": [
                (b"content-type", b"text/plain; charset=utf-8"),
                (b"content-length", str(len(body.encode())).encode()),
            ],
        }
    )
    await send({"type": "http.response.body", "body": body.encode(), "more_body": False})


class RequestGuardMiddleware:
    """Pure ASGI middleware: no BaseHTTPMiddleware, no _receive monkey-patching."""

    def __init__(self, app: ASGIApp, settings: Settings) -> None:
        self.app = app
        self._settings = settings
        self._sessionHits: dict[str, deque[float]] = defaultdict(deque)

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        if scope["type"] != "http":
            await self.app(scope, receive, send)
            return

        s = self._settings
        client = scope.get("client") or (None, None)
        sessionKey = client[0] if client and client[0] else "anon"
        method: str = scope.get("method", "GET")
        path: str = scope.get("path", "")

        # Skip rate-limit entirely for static assets, docs, and read-only API
        # polling endpoints. GETs for pages are also exempt — only body-bearing
        # methods (POST/PUT/PATCH) need rate-limiting.
        if any(path.startswith(p) for p in _NO_RATE_LIMIT_PREFIXES) or method == "GET":
            await self.app(scope, receive, send)
            return

        # ── B1: rate-limit body-bearing requests by client host ─────────
        now = time.time()
        window = self._sessionHits[sessionKey]
        while window and now - window[0] > 60:
            window.popleft()
        if len(window) >= s.rate_limit_messages_per_min:
            await _sendPlainResponse(send, 429, "rate limit exceeded")
            return
        window.append(now)

        # ── B1: length + charset checks — only for body-bearing methods ─
        if method in _BODY_METHODS:
            bufferedMessages: list[Message] = []
            body = bytearray()
            moreBody = True
            while moreBody:
                message = await receive()
                if message["type"] == "http.disconnect":
                    # Client gave up before we could validate — nothing to do.
                    return
                if message["type"] != "http.request":
                    # Unknown message; forward to downstream to let it handle.
                    bufferedMessages.append(message)
                    continue
                bufferedMessages.append(message)
                chunk = message.get("body", b"") or b""
                body.extend(chunk)
                moreBody = bool(message.get("more_body", False))

            parsed: dict[str, Any] = {}
            if body:
                try:
                    parsed = json.loads(bytes(body))
                    if not isinstance(parsed, dict):
                        parsed = {}
                except (ValueError, TypeError):
                    parsed = {}

            msg = str(parsed.get("message", ""))
            just = str(parsed.get("justification", ""))

            if len(msg) > s.max_message_chars:
                await _sendPlainResponse(
                    send, 413, f"message exceeds {s.max_message_chars} chars"
                )
                return
            if len(just) > s.max_justification_chars:
                await _sendPlainResponse(
                    send,
                    413,
                    f"justification exceeds {s.max_justification_chars} chars",
                )
                return
            for text in (msg, just):
                if any(not _isSafeChar(c) for c in text):
                    await _sendPlainResponse(send, 400, "request contains control characters")
                    return

            # Stash quota snapshot on scope.state for downstream handlers.
            stateObj = scope.get("state")
            if stateObj is not None:
                stateObj["userQuotaSnapshot"] = {
                    "sessionKey": sessionKey,
                    "timestamp": now,
                    "rateWindowDepth": len(window),
                }

            # Replay buffered body messages, then respond http.disconnect
            # to any further receive() calls (per ASGI protocol).
            iterator = iter(bufferedMessages)

            async def replayReceive() -> Message:
                try:
                    return next(iterator)
                except StopIteration:
                    return {"type": "http.disconnect"}

            await self.app(scope, replayReceive, send)
            return

        # GET / HEAD / OPTIONS / DELETE — no body to inspect; forward as-is.
        stateObj = scope.get("state")
        if stateObj is not None:
            stateObj["userQuotaSnapshot"] = {
                "sessionKey": sessionKey,
                "timestamp": now,
                "rateWindowDepth": len(window),
            }
        await self.app(scope, receive, send)
