"""Every boundary trip writes exactly one audit row (B7)."""

from unittest.mock import AsyncMock, patch

import pytest

from agentic_claims.agents.abuse_guard.node import abuseGuardNode


@pytest.mark.asyncio
async def testCoherenceFailureEmitsOneAuditRow() -> None:
    """Coherence gate failure writes exactly one coherence_failed row via writeGuardEvent."""
    writes: list[dict] = []

    async def spy(**kw):
        writes.append(kw)

    state = {
        "claimId": "C",
        "dbClaimId": 7,
        "extractedReceipt": {"fields": {"category": "meals"}},
        "userJustification": "x",  # too short → coherence fails
    }
    with patch("agentic_claims.agents.abuse_guard.node.writeGuardEvent", spy), \
         patch("agentic_claims.agents.abuse_guard.node.checkReceiptJustificationAlignment",
               AsyncMock(return_value=(True, "ok"))):
        await abuseGuardNode(state)

    coherenceWrites = [w for w in writes if w.get("action") == "coherence_failed"]
    assert len(coherenceWrites) == 1
    assert coherenceWrites[0]["dbClaimId"] == 7


@pytest.mark.asyncio
async def testCrossCheckFailureEmitsOneAuditRow() -> None:
    """Cross-check failure writes exactly one cross_check_failed row."""
    writes: list[dict] = []

    async def spy(**kw):
        writes.append(kw)

    state = {
        "claimId": "C",
        "dbClaimId": 7,
        "extractedReceipt": {"fields": {"category": "accommodation"}},
        "userJustification": "client lunch at Acme Corp for project kickoff",  # passes coherence
    }
    with patch("agentic_claims.agents.abuse_guard.node.writeGuardEvent", spy), \
         patch("agentic_claims.agents.abuse_guard.node.checkReceiptJustificationAlignment",
               AsyncMock(return_value=(False, "category mismatch"))):
        await abuseGuardNode(state)

    crossCheckWrites = [w for w in writes if w.get("action") == "cross_check_failed"]
    assert len(crossCheckWrites) == 1


@pytest.mark.asyncio
async def testBothFailuresEmitTwoAuditRows() -> None:
    """When both guards fail, exactly two audit rows are emitted (one per failure)."""
    writes: list[dict] = []

    async def spy(**kw):
        writes.append(kw)

    state = {
        "claimId": "C",
        "dbClaimId": 7,
        "extractedReceipt": {"fields": {"category": "meals"}},
        "userJustification": "x",  # fails coherence
    }
    with patch("agentic_claims.agents.abuse_guard.node.writeGuardEvent", spy), \
         patch("agentic_claims.agents.abuse_guard.node.checkReceiptJustificationAlignment",
               AsyncMock(return_value=(False, "mismatch"))):
        await abuseGuardNode(state)

    assert len(writes) == 2
    actions = {w["action"] for w in writes}
    assert actions == {"coherence_failed", "cross_check_failed"}


@pytest.mark.asyncio
async def testCleanPathEmitsZeroAuditRows() -> None:
    """When both guards pass, zero audit rows are emitted."""
    writes: list[dict] = []

    async def spy(**kw):
        writes.append(kw)

    state = {
        "claimId": "C",
        "dbClaimId": 7,
        "extractedReceipt": {"fields": {"category": "meals", "merchant": "ABC", "totalAmountSgd": 40}},
        "userJustification": "client lunch meeting with Acme Corp",
    }
    with patch("agentic_claims.agents.abuse_guard.node.writeGuardEvent", spy), \
         patch("agentic_claims.agents.abuse_guard.node.checkReceiptJustificationAlignment",
               AsyncMock(return_value=(True, "ok"))):
        await abuseGuardNode(state)

    assert writes == []
