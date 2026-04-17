"""Receipt ↔ justification cross-check (B4) tests."""

from unittest.mock import AsyncMock, patch

import pytest

from agentic_claims.agents.abuse_guard.crossCheck import checkReceiptJustificationAlignment


@pytest.mark.asyncio
async def testConsistentJustificationReturnsOk() -> None:
    fakeResponse = type("R", (), {"content": '{"consistent": true, "reason": "meal matches"}'})()
    with patch("agentic_claims.agents.abuse_guard.crossCheck.buildAgentLlm") as mockBuild:
        mockBuild.return_value.ainvoke = AsyncMock(return_value=fakeResponse)
        ok, reason = await checkReceiptJustificationAlignment(
            receipt={"category": "meals", "merchant": "ABC Cafe", "totalAmountSgd": 45.0},
            justification="client lunch at ABC Cafe",
        )
        assert ok is True
        assert "meal" in reason.lower()


@pytest.mark.asyncio
async def testInconsistentJustificationReturnsFail() -> None:
    fakeResponse = type(
        "R",
        (),
        {"content": '{"consistent": false, "reason": "receipt is hotel but user claims meal"}'},
    )()
    with patch("agentic_claims.agents.abuse_guard.crossCheck.buildAgentLlm") as mockBuild:
        mockBuild.return_value.ainvoke = AsyncMock(return_value=fakeResponse)
        ok, reason = await checkReceiptJustificationAlignment(
            receipt={"category": "accommodation", "merchant": "Hyatt", "totalAmountSgd": 300.0},
            justification="team lunch",
        )
        assert ok is False


@pytest.mark.asyncio
async def testMalformedLlmResponseTreatedAsInconsistent() -> None:
    fakeResponse = type("R", (), {"content": "not json at all"})()
    with patch("agentic_claims.agents.abuse_guard.crossCheck.buildAgentLlm") as mockBuild:
        mockBuild.return_value.ainvoke = AsyncMock(return_value=fakeResponse)
        ok, _ = await checkReceiptJustificationAlignment(
            receipt={"category": "meals", "merchant": "x", "totalAmountSgd": 1.0},
            justification="client dinner",
        )
        assert ok is False


@pytest.mark.asyncio
async def testNoJustificationSkipped() -> None:
    """Empty justification ⇒ True (no justification means no mismatch), no LLM call."""
    ok, reason = await checkReceiptJustificationAlignment(
        receipt={"category": "meals"}, justification=""
    )
    assert ok is True
    assert "no justification" in reason.lower()


@pytest.mark.asyncio
async def testLlmExceptionTreatedAsInconsistent() -> None:
    with patch("agentic_claims.agents.abuse_guard.crossCheck.buildAgentLlm") as mockBuild:
        mockBuild.return_value.ainvoke = AsyncMock(side_effect=RuntimeError("boom"))
        ok, _ = await checkReceiptJustificationAlignment(
            receipt={"category": "meals"}, justification="client lunch"
        )
        assert ok is False
