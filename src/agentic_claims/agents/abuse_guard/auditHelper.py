"""Audit helper — shared writeGuardEvent for all Spec A boundary trips (B7).

Writes a single row to audit_log via the mcp-db `insertAuditLog` tool.
Audit failures are swallowed so they never break the agent flow, but they
are logged at WARNING so the logs dashboard surfaces them.
"""

from __future__ import annotations

import json
import logging
from typing import Any, Optional

from agentic_claims.agents.intake.utils.mcpClient import mcpCallTool
from agentic_claims.core.config import getSettings

logger = logging.getLogger(__name__)


async def writeGuardEvent(
    *,
    dbClaimId: Optional[int],
    action: str,
    details: dict[str, Any],
    actor: str = "abuse_guard",
) -> None:
    """Write a single audit_log row via mcp-db.insertAuditLog.

    Args:
        dbClaimId: FK to claims.id. If None, the helper is a no-op (we
            can't write a row without a claim id). This happens early
            in the session before a claim exists.
        action: audit_log.action value (e.g. "coherence_failed").
        details: free-form dict serialized to audit_log.new_value as JSON.
        actor: audit_log.actor. Defaults to "abuse_guard".
    """
    if dbClaimId is None:
        logger.debug("writeGuardEvent skipped: dbClaimId not set yet (action=%s)", action)
        return

    settings = getSettings()
    try:
        await mcpCallTool(
            serverUrl=settings.db_mcp_url,
            toolName="insertAuditLog",
            arguments={
                "claimId": dbClaimId,
                "action": action,
                "newValue": json.dumps(details, default=str),
                "actor": actor,
                "oldValue": "",
            },
        )
    except Exception as exc:
        logger.warning("writeGuardEvent failed: action=%s error=%s", action, exc)
