"""Logs viewer router — /logs page showing recent errors by agent/component.

Reads Docker container logs via the Docker Engine API over the mounted
/var/run/docker.sock socket. This avoids needing Docker CLI inside the
app container.
"""

import json
import logging
import re
from datetime import datetime, timezone
from typing import Any

import httpx
from fastapi import APIRouter, Request

from agentic_claims.web.templating import templates

logger = logging.getLogger(__name__)
router = APIRouter()

# Docker Engine API via Unix socket
_DOCKER_SOCKET = "/var/run/docker.sock"
# Map compose service names to container name patterns
_SERVICE_CONTAINERS = {
    "app": "mmga-expense-app",
    "mcp-rag": "mmga-expense-mcp-rag",
    "mcp-db": "mmga-expense-mcp-db",
    "mcp-currency": "mmga-expense-mcp-currency",
    "mcp-email": "mmga-expense-mcp-email",
}


async def _getContainerLogs(containerName: str, tail: int = 150) -> list[str]:
    """Fetch logs from a Docker container via the Engine API."""
    try:
        transport = httpx.AsyncHTTPTransport(uds=_DOCKER_SOCKET)
        async with httpx.AsyncClient(transport=transport, base_url="http://docker") as client:
            # List containers to find the right one
            resp = await client.get(
                "/containers/json",
                params={"all": "true", "filters": json.dumps({"name": [containerName]})},
                timeout=5.0,
            )
            containers = resp.json()
            if not containers:
                return [f"Container '{containerName}' not found"]

            containerId = containers[0]["Id"]

            # Get logs
            resp = await client.get(
                f"/containers/{containerId}/logs",
                params={"stdout": "true", "stderr": "true", "tail": str(tail), "timestamps": "true"},
                timeout=10.0,
            )
            # Docker log stream has 8-byte header per frame; strip it
            raw = resp.content
            lines = []
            i = 0
            while i < len(raw):
                if i + 8 > len(raw):
                    break
                size = int.from_bytes(raw[i + 4 : i + 8], "big")
                i += 8
                if i + size > len(raw):
                    chunk = raw[i:].decode("utf-8", errors="replace").strip()
                else:
                    chunk = raw[i : i + size].decode("utf-8", errors="replace").strip()
                i += size
                if chunk:
                    lines.append(chunk)
            return lines
    except Exception as e:
        return [f"ERROR: Failed to read logs: {e}"]


def _parseLine(line: str, service: str) -> dict[str, Any]:
    """Parse a single log line into a structured entry."""
    level = "INFO"
    message = line
    timestamp = ""
    funcName = ""
    loggerName = ""

    # Strip Docker timestamp prefix (e.g. "2026-04-08T15:19:59.158189123Z ")
    tsMatch = re.match(r"^(\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}\.\d+Z?)\s+(.*)", line)
    if tsMatch:
        timestamp = tsMatch.group(1)[:23]  # trim nanoseconds
        message = tsMatch.group(2)

    # Try JSON structured log
    if '"levelname"' in message:
        try:
            data = json.loads(message)
            level = data.get("levelname", "INFO")
            message = data.get("message", message)
            timestamp = data.get("asctime", timestamp)
            funcName = data.get("funcName", "")
            loggerName = data.get("name", "")
        except (json.JSONDecodeError, TypeError):
            pass
    elif "ERROR" in message.upper():
        level = "ERROR"
    elif "WARNING" in message.upper():
        level = "WARNING"
    elif "Traceback" in message or "Exception" in message:
        level = "ERROR"

    return {
        "level": level,
        "message": message[:500],
        "timestamp": timestamp,
        "source": service,
        "funcName": funcName,
        "loggerName": loggerName,
    }


async def _parseDockerLogs(service: str, containerName: str, tail: int = 150) -> list[dict[str, Any]]:
    """Get and parse logs for a service."""
    rawLines = await _getContainerLogs(containerName, tail)
    return [_parseLine(line, service) for line in rawLines if line.strip()]


async def _getAgentLogs() -> dict[str, list[dict]]:
    """Get logs from all services, grouped by service name."""
    import asyncio

    services = {
        "app": "FastAPI + LangGraph Agents",
        "mcp-rag": "MCP-RAG (Policy Search)",
        "mcp-db": "MCP-DB (Database)",
        "mcp-currency": "MCP-Currency",
        "mcp-email": "MCP-Email",
    }

    # Fetch all logs concurrently
    tasks = {
        svc: _parseDockerLogs(svc, _SERVICE_CONTAINERS[svc], tail=150)
        for svc in services
    }
    results = await asyncio.gather(*tasks.values())

    allLogs: dict[str, dict] = {}
    for (service, label), entries in zip(services.items(), results):
        allLogs[service] = {
            "label": label,
            "entries": entries,
            "errors": [e for e in entries if e["level"] in ("ERROR", "CRITICAL")],
            "warnings": [e for e in entries if e["level"] == "WARNING"],
            "totalLines": len(entries),
        }

    return allLogs


@router.get("/logs")
async def logsPage(request: Request):
    """Render the logs viewer page."""
    allLogs = await _getAgentLogs()

    # Summary counts
    totalErrors = sum(len(s["errors"]) for s in allLogs.values())
    totalWarnings = sum(len(s["warnings"]) for s in allLogs.values())

    currentUser = {
        "role": request.session.get("role", ""),
        "displayName": request.session.get("display_name", ""),
    }

    return templates.TemplateResponse(
        request,
        "logs.html",
        context={
            "activePage": "logs",
            "logs": allLogs,
            "totalErrors": totalErrors,
            "totalWarnings": totalWarnings,
            "userRole": currentUser["role"],
            "displayName": currentUser["displayName"],
            "username": request.session.get("username", ""),
            "timestamp": datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S UTC"),
        },
    )


@router.get("/logs/json")
async def logsJson(request: Request):
    """Return logs as JSON for programmatic access."""
    allLogs = await _getAgentLogs()
    return {
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "services": {
            k: {"label": v["label"], "errors": v["errors"], "warnings": v["warnings"],
                "errorCount": len(v["errors"]), "warningCount": len(v["warnings"]), "totalLines": v["totalLines"]}
            for k, v in allLogs.items()
        },
    }
