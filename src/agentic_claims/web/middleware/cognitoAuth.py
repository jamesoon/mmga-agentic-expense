"""Cognito JWT authentication middleware.

Replaces session-based AuthMiddleware. Decodes the Cognito RS256 ID token
from the Authorization: Bearer header, validates signature and expiry,
and populates request.state.user for downstream route handlers.

Falls back to legacy session-based auth during the transition window
(when both SessionMiddleware and this are active simultaneously).
"""

import logging
import time
from typing import Any

import httpx
from jose import JWTError, jwk, jwt
from jose.utils import base64url_decode
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import JSONResponse, Response

logger = logging.getLogger(__name__)

# Paths exempt from auth — must match main.py _PUBLIC_PATHS/_PUBLIC_PREFIXES
_PUBLIC_PATHS = {"/login", "/logout", "/llmasjudge", "/architecture", "/health"}
_PUBLIC_PREFIXES = (
    "/static/",
    "/llmasjudge/",
    "/architecture/",
    "/health/",
    "/auth/",
)
_API_PREFIXES = ("/chat/", "/api/")

# JWKS is fetched once and cached in memory for the process lifetime.
_jwksCache: dict[str, Any] = {}
_jwksCacheTime: float = 0.0
_JWKS_TTL = 3600  # refresh JWKS every hour


def _cognitoJwksUrl(userPoolId: str, region: str) -> str:
    return f"https://cognito-idp.{region}.amazonaws.com/{userPoolId}/.well-known/jwks.json"


async def _fetchJwks(userPoolId: str, region: str) -> dict[str, Any]:
    global _jwksCache, _jwksCacheTime
    now = time.monotonic()
    if _jwksCache and (now - _jwksCacheTime) < _JWKS_TTL:
        return _jwksCache
    url = _cognitoJwksUrl(userPoolId, region)
    async with httpx.AsyncClient(timeout=5.0) as client:
        resp = await client.get(url)
        resp.raise_for_status()
        _jwksCache = resp.json()
        _jwksCacheTime = now
        logger.debug("JWKS refreshed from Cognito")
    return _jwksCache


def _getPublicKey(jwks: dict, kid: str) -> Any:
    for key in jwks.get("keys", []):
        if key["kid"] == kid:
            return jwk.construct(key)
    return None


def _decodeCognitoToken(token: str, jwks: dict, userPoolId: str, region: str, clientId: str) -> dict:
    """Decode and verify a Cognito ID token. Raises JWTError on failure."""
    headers = jwt.get_unverified_headers(token)
    kid = headers.get("kid")
    publicKey = _getPublicKey(jwks, kid)
    if publicKey is None:
        raise JWTError(f"No matching key found for kid={kid}")

    issuer = f"https://cognito-idp.{region}.amazonaws.com/{userPoolId}"
    claims = jwt.decode(
        token,
        publicKey,
        algorithms=["RS256"],
        audience=clientId,
        issuer=issuer,
        options={"verify_at_hash": False},
    )
    return claims


def _userFromClaims(claims: dict) -> dict:
    """Build a normalised user dict from Cognito JWT claims."""
    groups: list[str] = claims.get("cognito:groups", [])
    # Primary role is first group; default to "users"
    role = groups[0] if groups else "users"
    # Strip trailing "s" to match legacy role strings (reviewers→reviewer etc.)
    legacyRole = role.rstrip("s") if role.endswith("s") and role != "users" else (
        "user" if role == "users" else role
    )
    return {
        "userId": claims.get("sub"),
        "username": claims.get("cognito:username") or claims.get("preferred_username", ""),
        "role": legacyRole,
        "groups": groups,
        "employeeId": claims.get("custom:employee_id", ""),
        "displayName": claims.get("custom:display_name", ""),
        "email": claims.get("email", ""),
        "sub": claims.get("sub"),
    }


class CognitoAuthMiddleware(BaseHTTPMiddleware):
    """Validate Cognito Bearer token and populate request.state.user.

    Falls back to legacy session dict when no Bearer header is present
    (supports dual-auth transition window).
    """

    def __init__(self, app, userPoolId: str, region: str, clientId: str):
        super().__init__(app)
        self.userPoolId = userPoolId
        self.region = region
        self.clientId = clientId

    async def dispatch(self, request: Request, callNext) -> Response:
        path = request.url.path

        # Always pass public paths through
        if path in _PUBLIC_PATHS or any(path.startswith(p) for p in _PUBLIC_PREFIXES):
            return await callNext(request)

        # 1. Try Bearer token (Cognito)
        authHeader = request.headers.get("Authorization", "")
        if authHeader.startswith("Bearer "):
            token = authHeader[7:]
            try:
                jwks = await _fetchJwks(self.userPoolId, self.region)
                claims = _decodeCognitoToken(token, jwks, self.userPoolId, self.region, self.clientId)
                request.state.user = _userFromClaims(claims)
                return await callNext(request)
            except JWTError as exc:
                logger.warning("Cognito JWT invalid: %s", exc)
                return JSONResponse({"detail": "Invalid or expired token"}, status_code=401)
            except Exception as exc:
                logger.error("Cognito auth error: %s", exc)
                return JSONResponse({"detail": "Authentication error"}, status_code=500)

        # 2. Fall back to legacy session (transition window)
        sessionUserId = getattr(request, "session", {}).get("user_id") if hasattr(request, "session") else None
        if sessionUserId:
            request.state.user = {
                "userId": sessionUserId,
                "username": request.session.get("username", ""),
                "role": request.session.get("role", "user"),
                "groups": [request.session.get("role", "users") + "s"],
                "employeeId": request.session.get("employee_id", ""),
                "displayName": request.session.get("display_name", ""),
                "email": "",
                "sub": None,
            }
            return await callNext(request)

        # 3. Not authenticated
        if any(path.startswith(p) for p in _API_PREFIXES):
            return JSONResponse({"detail": "Not authenticated"}, status_code=401)
        from starlette.responses import RedirectResponse
        return RedirectResponse("/login", status_code=302)
