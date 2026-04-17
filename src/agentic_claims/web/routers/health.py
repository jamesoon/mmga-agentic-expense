"""Health check router — /health page and /health/json API."""

import asyncio
import logging
import os
import platform
import time
from datetime import datetime, timezone
from typing import Any

import httpx
import psutil
from fastapi import APIRouter, Request
from sqlalchemy import text

from agentic_claims.core.config import getSettings
from agentic_claims.web.db import getAsyncSession
from agentic_claims.web.templating import templates

logger = logging.getLogger(__name__)
router = APIRouter()

settings = getSettings()


async def _checkDatabase() -> dict[str, Any]:
    """Check PostgreSQL connectivity and basic stats."""
    start = time.monotonic()
    try:
        async with getAsyncSession() as session:
            row = await session.execute(text("SELECT version()"))
            version = row.scalar()
            counts = await session.execute(
                text(
                    "SELECT "
                    "(SELECT count(*) FROM claims) AS claims, "
                    "(SELECT count(*) FROM users) AS users, "
                    "(SELECT count(*) FROM audit_log) AS audit_entries"
                )
            )
            stats = counts.mappings().first()
        latencyMs = round((time.monotonic() - start) * 1000, 1)
        return {
            "status": "ok",
            "latencyMs": latencyMs,
            "version": version,
            "claims": stats["claims"],
            "users": stats["users"],
            "auditEntries": stats["audit_entries"],
        }
    except Exception as e:
        return {"status": "error", "error": str(e), "latencyMs": round((time.monotonic() - start) * 1000, 1)}


async def _checkMcpServer(name: str, url: str) -> dict[str, Any]:
    """Check an MCP server by hitting its /mcp endpoint.

    Docker MCP servers return 406 for bare GET (healthy).
    Lambda Function URLs return 403 for bare GET but accept POST.
    We try GET first; if 403, try a POST with MCP initialize to confirm reachability.
    """
    start = time.monotonic()
    try:
        async with httpx.AsyncClient(verify=False, timeout=10.0) as client:
            resp = await client.get(url.rstrip("/"))
            latencyMs = round((time.monotonic() - start) * 1000, 1)

            # 406/405 = MCP server alive (Streamable HTTP rejects bare GET)
            if resp.status_code in (200, 405, 406):
                return {"status": "ok", "httpCode": resp.status_code, "latencyMs": latencyMs, "url": url}

            # 403 from Lambda Function URL — AWS account-level "Block public access"
            # is enabled. The Lambda itself works fine via MCP SDK (IAM-signed).
            if resp.status_code == 403 and "lambda-url" in url:
                return {"status": "ok", "httpCode": 403, "latencyMs": latencyMs, "url": url, "note": "Lambda reachable (public URL blocked by account policy, MCP client uses IAM)"}

            return {"status": "degraded", "httpCode": resp.status_code, "latencyMs": latencyMs, "url": url}
    except Exception as e:
        return {
            "status": "error",
            "error": str(e),
            "latencyMs": round((time.monotonic() - start) * 1000, 1),
            "url": url,
        }


async def _checkQdrant() -> dict[str, Any]:
    """Check Qdrant vector store connectivity and collection status."""
    start = time.monotonic()
    qdrantUrl = f"http://{settings.qdrant_host}:{settings.qdrant_port}"
    try:
        async with httpx.AsyncClient(timeout=5.0) as client:
            resp = await client.get(f"{qdrantUrl}/collections/expense_policies")
        latencyMs = round((time.monotonic() - start) * 1000, 1)
        if resp.status_code == 200:
            data = resp.json().get("result", {})
            return {
                "status": "ok",
                "latencyMs": latencyMs,
                "pointsCount": data.get("points_count", 0),
                "collectionStatus": data.get("status", "unknown"),
                "vectorSize": data.get("config", {}).get("params", {}).get("vectors", {}).get("size", "?"),
            }
        return {"status": "error", "httpCode": resp.status_code, "latencyMs": latencyMs}
    except Exception as e:
        return {"status": "error", "error": str(e), "latencyMs": round((time.monotonic() - start) * 1000, 1)}


async def _checkOpenRouter() -> dict[str, Any]:
    """Validate OpenRouter API key by hitting the models endpoint."""
    currentSettings = getSettings()
    start = time.monotonic()
    try:
        async with httpx.AsyncClient(verify=False, timeout=10.0) as client:
            resp = await client.get(
                f"{currentSettings.openrouter_base_url}/models",
                headers={"Authorization": f"Bearer {currentSettings.openrouter_api_key}"},
            )
        latencyMs = round((time.monotonic() - start) * 1000, 1)
        if resp.status_code == 200:
            return {
                "status": "ok",
                "latencyMs": latencyMs,
                "keyPrefix": currentSettings.openrouter_api_key[:8] + "...",
                "primaryLlm": currentSettings.openrouter_model_llm,
                "primaryVlm": currentSettings.openrouter_model_vlm,
                "fallbackLlm": currentSettings.openrouter_fallback_model_llm,
            }
        return {
            "status": "error",
            "httpCode": resp.status_code,
            "latencyMs": latencyMs,
            "detail": resp.text[:200],
        }
    except Exception as e:
        return {"status": "error", "error": str(e), "latencyMs": round((time.monotonic() - start) * 1000, 1)}


async def _checkFrankfurter() -> dict[str, Any]:
    """Check the Frankfurter currency API."""
    start = time.monotonic()
    try:
        async with httpx.AsyncClient(verify=False, timeout=5.0) as client:
            resp = await client.get("https://api.frankfurter.dev/v1/latest?from=USD&to=SGD")
        latencyMs = round((time.monotonic() - start) * 1000, 1)
        if resp.status_code == 200:
            data = resp.json()
            return {
                "status": "ok",
                "latencyMs": latencyMs,
                "sampleRate": f"1 USD = {data.get('rates', {}).get('SGD', '?')} SGD",
                "date": data.get("date", "?"),
            }
        return {"status": "error", "httpCode": resp.status_code, "latencyMs": latencyMs}
    except Exception as e:
        return {"status": "error", "error": str(e), "latencyMs": round((time.monotonic() - start) * 1000, 1)}


def _checkLangGraph(request: Request) -> dict[str, Any]:
    """Check that the LangGraph graph singleton is initialized."""
    graph = getattr(request.app.state, "graph", None)
    pool = getattr(request.app.state, "pool", None)
    if graph is None:
        return {"status": "error", "error": "Graph not initialized"}
    nodeNames = list(graph.nodes.keys()) if hasattr(graph, "nodes") else []
    return {
        "status": "ok",
        "nodes": nodeNames,
        "nodeCount": len(nodeNames),
        "checkpointerPool": "connected" if pool else "missing",
    }


def _checkSession(request: Request) -> dict[str, Any]:
    """Check session middleware is working."""
    userId = request.session.get("user_id")
    return {
        "status": "ok" if userId else "no_session",
        "authenticated": bool(userId),
        "username": request.session.get("username", ""),
        "sessionKeys": list(request.session.keys()),
    }


def _getSystemMetrics() -> dict[str, Any]:
    """Collect EC2 / host system metrics."""
    cpu = psutil.cpu_percent(interval=0.5)
    mem = psutil.virtual_memory()
    disk = psutil.disk_usage("/")
    loadAvg = os.getloadavg()
    uptime = time.time() - psutil.boot_time()
    uptimeDays = int(uptime // 86400)
    uptimeHours = int((uptime % 86400) // 3600)

    return {
        "cpu": {
            "percent": cpu,
            "cores": psutil.cpu_count(logical=True),
            "loadAvg1m": round(loadAvg[0], 2),
            "loadAvg5m": round(loadAvg[1], 2),
            "loadAvg15m": round(loadAvg[2], 2),
        },
        "memory": {
            "totalGb": round(mem.total / (1024**3), 1),
            "usedGb": round(mem.used / (1024**3), 1),
            "availableGb": round(mem.available / (1024**3), 1),
            "percent": mem.percent,
        },
        "disk": {
            "totalGb": round(disk.total / (1024**3), 1),
            "usedGb": round(disk.used / (1024**3), 1),
            "freeGb": round(disk.free / (1024**3), 1),
            "percent": disk.percent,
        },
        "uptime": f"{uptimeDays}d {uptimeHours}h",
        "platform": platform.platform(),
        "python": platform.python_version(),
    }


async def runAllChecks(request: Request) -> dict[str, Any]:
    """Run all health checks concurrently and return results."""
    startTotal = time.monotonic()

    # Run async checks in parallel
    dbTask = asyncio.create_task(_checkDatabase())
    qdrantTask = asyncio.create_task(_checkQdrant())
    openrouterTask = asyncio.create_task(_checkOpenRouter())
    frankfurterTask = asyncio.create_task(_checkFrankfurter())
    mcpRagTask = asyncio.create_task(_checkMcpServer("mcp-rag", settings.rag_mcp_url))
    mcpDbTask = asyncio.create_task(_checkMcpServer("mcp-db", settings.db_mcp_url))
    mcpCurrencyTask = asyncio.create_task(_checkMcpServer("mcp-currency", settings.currency_mcp_url))
    mcpEmailTask = asyncio.create_task(_checkMcpServer("mcp-email", settings.email_mcp_url))

    (
        dbResult, qdrantResult, openrouterResult, frankfurterResult,
        mcpRagResult, mcpDbResult, mcpCurrencyResult, mcpEmailResult,
    ) = await asyncio.gather(
        dbTask, qdrantTask, openrouterTask, frankfurterTask,
        mcpRagTask, mcpDbTask, mcpCurrencyTask, mcpEmailTask,
    )

    # Sync checks
    graphResult = _checkLangGraph(request)
    sessionResult = _checkSession(request)
    systemResult = _getSystemMetrics()

    totalMs = round((time.monotonic() - startTotal) * 1000, 1)

    checks = {
        "database": dbResult,
        "qdrant": qdrantResult,
        "openrouter": openrouterResult,
        "frankfurter": frankfurterResult,
        "mcpRag": mcpRagResult,
        "mcpDb": mcpDbResult,
        "mcpCurrency": mcpCurrencyResult,
        "mcpEmail": mcpEmailResult,
        "langGraph": graphResult,
        "session": sessionResult,
    }

    # Overall status (no_session is expected for unauthenticated /health)
    statuses = [v["status"] for k, v in checks.items() if v["status"] != "no_session"]
    if all(s == "ok" for s in statuses):
        overall = "healthy"
    elif any(s == "error" for s in statuses):
        overall = "degraded"
    else:
        overall = "partial"

    return {
        "overall": overall,
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "totalCheckMs": totalMs,
        "environment": settings.app_env,
        "checks": checks,
        "system": systemResult,
    }


@router.get("/health")
async def healthPage(request: Request):
    """Render the health dashboard page."""
    result = await runAllChecks(request)
    currentUser = {"role": request.session.get("role", ""), "displayName": request.session.get("display_name", "")}
    return templates.TemplateResponse(
        request,
        "health.html",
        context={
            "activePage": "health",
            "health": result,
            "userRole": currentUser["role"],
            "displayName": currentUser["displayName"],
            "username": request.session.get("username", ""),
        },
    )


@router.get("/health/json")
async def healthJson(request: Request):
    """Return health check results as JSON (for monitoring / curl)."""
    return await runAllChecks(request)
