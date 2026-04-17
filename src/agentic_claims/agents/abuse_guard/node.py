"""abuseGuardNode — LangGraph node coordinating B2 coherence + B4 cross-check.

Runs between intake_gpt and evaluatorGate. Writes abuseFlags to state.
Does not modify user-facing messages.
"""

from __future__ import annotations

import logging
from typing import Any

from agentic_claims.agents.abuse_guard.auditHelper import writeGuardEvent
from agentic_claims.agents.abuse_guard.coherence import checkJustificationCoherence
from agentic_claims.agents.abuse_guard.crossCheck import checkReceiptJustificationAlignment
from agentic_claims.core.logging import logEvent
from agentic_claims.core.state import ClaimState

logger = logging.getLogger(__name__)


async def abuseGuardNode(state: ClaimState) -> dict[str, Any]:
    claimId = state.get("claimId", "unknown")
    dbClaimId = state.get("dbClaimId")
    receipt = (state.get("extractedReceipt") or {}).get("fields") or (
        state.get("extractedReceipt") or {}
    )
    if not isinstance(receipt, dict):
        receipt = {}
    justification = state.get("userJustification") or ""

    coherenceOk, coherenceReason = checkJustificationCoherence(justification)
    if not coherenceOk:
        await writeGuardEvent(
            dbClaimId=dbClaimId,
            action="coherence_failed",
            details={
                "reason": coherenceReason,
                "justificationChars": len(justification),
            },
        )

    crossCheckOk, crossCheckReason = await checkReceiptJustificationAlignment(
        receipt=receipt,
        justification=justification,
    )
    if not crossCheckOk:
        await writeGuardEvent(
            dbClaimId=dbClaimId,
            action="cross_check_failed",
            details={"reason": crossCheckReason},
        )

    abuseFlags: dict[str, Any] = {
        "coherenceOk": coherenceOk,
        "coherenceReason": coherenceReason,
        "crossCheckOk": crossCheckOk,
        "crossCheckReason": crossCheckReason,
        "injectionSanitized": False,
        "injectionPatterns": [],
        "hardCapExceeded": False,
        "hardCapReasons": [],
        "auditRefs": [],
    }

    logEvent(
        logger,
        "abuse_guard.completed",
        logCategory="agent",
        agent="abuse_guard",
        claimId=claimId,
        coherenceOk=coherenceOk,
        crossCheckOk=crossCheckOk,
        message="abuseGuard completed",
    )
    return {"abuseFlags": abuseFlags}
