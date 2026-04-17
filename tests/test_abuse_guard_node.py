"""abuseGuardNode orchestration tests."""

from unittest.mock import AsyncMock, patch

import pytest

from agentic_claims.agents.abuse_guard.node import abuseGuardNode


@pytest.mark.asyncio
async def testAllPasses() -> None:
    state = {
        "claimId": "C1",
        "extractedReceipt": {"fields": {"category": "meals", "merchant": "ABC", "totalAmountSgd": 40}},
        "userJustification": "client lunch meeting with Acme Corp",
        "dbClaimId": 123,
    }
    with patch("agentic_claims.agents.abuse_guard.node.checkReceiptJustificationAlignment",
               AsyncMock(return_value=(True, "ok"))), \
         patch("agentic_claims.agents.abuse_guard.node.writeGuardEvent", AsyncMock()):
        out = await abuseGuardNode(state)
    flags = out["abuseFlags"]
    assert flags["coherenceOk"] is True
    assert flags["crossCheckOk"] is True


@pytest.mark.asyncio
async def testCoherenceFailureRecorded() -> None:
    state = {
        "claimId": "C1",
        "extractedReceipt": {"fields": {"category": "meals"}},
        "userJustification": "asdf",  # fails coherence
    }
    with patch("agentic_claims.agents.abuse_guard.node.checkReceiptJustificationAlignment",
               AsyncMock(return_value=(True, "ok"))), \
         patch("agentic_claims.agents.abuse_guard.node.writeGuardEvent", AsyncMock()):
        out = await abuseGuardNode(state)
    assert out["abuseFlags"]["coherenceOk"] is False


@pytest.mark.asyncio
async def testCrossCheckFailureRecorded() -> None:
    state = {
        "claimId": "C1",
        "extractedReceipt": {"fields": {"category": "accommodation"}},
        "userJustification": "client lunch meeting at hotel conference room",
    }
    with patch("agentic_claims.agents.abuse_guard.node.checkReceiptJustificationAlignment",
               AsyncMock(return_value=(False, "category mismatch"))), \
         patch("agentic_claims.agents.abuse_guard.node.writeGuardEvent", AsyncMock()):
        out = await abuseGuardNode(state)
    assert out["abuseFlags"]["crossCheckOk"] is False
