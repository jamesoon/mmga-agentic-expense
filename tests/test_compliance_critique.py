"""Self-critique (B6) tests."""

from unittest.mock import AsyncMock, patch

import pytest

from agentic_claims.agents.compliance.critique import runSelfCritique


@pytest.mark.asyncio
async def testCritiqueAgreesNoOp() -> None:
    fake = type(
        "R",
        (),
        {"content": '{"agree": true, "verdict": "pass", "reasoning": "clauses support pass"}'},
    )()
    with patch("agentic_claims.agents.compliance.critique.buildAgentLlm") as mockBuild:
        mockBuild.return_value.ainvoke = AsyncMock(return_value=fake)
        result = await runSelfCritique(
            originalVerdict="pass", context={"violations": [], "justification": ""}
        )
    assert result["critiqueAgrees"] is True
    assert result["finalVerdict"] == "pass"


@pytest.mark.asyncio
async def testCritiqueDisagreesFlips() -> None:
    fake = type(
        "R",
        (),
        {"content": '{"agree": false, "verdict": "requiresReview", "reasoning": "flagged"}'},
    )()
    with patch("agentic_claims.agents.compliance.critique.buildAgentLlm") as mockBuild:
        mockBuild.return_value.ainvoke = AsyncMock(return_value=fake)
        result = await runSelfCritique(
            originalVerdict="pass", context={"violations": [], "justification": ""}
        )
    assert result["critiqueAgrees"] is False
    assert result["finalVerdict"] == "requiresReview"


@pytest.mark.asyncio
async def testCritiqueMalformedDefaultsToReview() -> None:
    fake = type("R", (), {"content": "not json"})()
    with patch("agentic_claims.agents.compliance.critique.buildAgentLlm") as mockBuild:
        mockBuild.return_value.ainvoke = AsyncMock(return_value=fake)
        result = await runSelfCritique(originalVerdict="pass", context={})
    assert result["finalVerdict"] == "requiresReview"


@pytest.mark.asyncio
async def testCritiqueDisabledReturnsAgree() -> None:
    # Passing a settings override with critique disabled should short-circuit without an LLM call.
    class _Stub:
        compliance_critique_enabled = False
        compliance_critique_model = None
        compliance_critique_temperature = 0.0

    result = await runSelfCritique(
        originalVerdict="pass",
        context={},
        settingsOverride=_Stub(),
    )
    assert result["critiqueAgrees"] is True
    assert result["finalVerdict"] == "pass"
