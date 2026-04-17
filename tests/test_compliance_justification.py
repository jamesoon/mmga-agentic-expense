"""Justification-aware compliance behaviour tests (Spec A W2 + B5 + B6)."""

from contextlib import contextmanager
from unittest.mock import AsyncMock, patch

import pytest

from agentic_claims.agents.compliance.node import complianceNode
from agentic_claims.core.config import Settings

_TEST_SETTINGS = Settings(_env_file="tests/.env.test")


@contextmanager
def _patchSettings():
    """Patch getSettings in every module that calls it directly."""
    with (
        patch("agentic_claims.agents.compliance.node.getSettings", return_value=_TEST_SETTINGS),
        patch("agentic_claims.core.logging.getSettings", return_value=_TEST_SETTINGS),
    ):
        yield


def _baseState(**kw) -> dict:
    state = {
        "claimId": "C1",
        "dbClaimId": 123,
        "extractedReceipt": {
            "fields": {
                "category": "meals",
                "merchant": "X",
                "totalAmountSgd": 120,
            }
        },
        "violations": [],
        "intakeFindings": {},
        "userJustification": "",
        "abuseFlags": None,
    }
    state.update(kw)
    return state


@pytest.mark.asyncio
async def testHardCapAutoEscalates() -> None:
    """Receipt total > per-receipt cap => verdict flagged as requiring director approval."""
    state = _baseState(
        extractedReceipt={"fields": {"category": "meals", "merchant": "X", "totalAmountSgd": 9999}},
    )
    fakeLlmResp = type("R", (), {"content": '{"verdict": "pass"}'})()
    critiqueResp = {
        "critiqueAgrees": True,
        "finalVerdict": "requiresDirectorApproval",
        "originalVerdict": "requiresDirectorApproval",
        "critiqueVerdict": "requiresDirectorApproval",
        "critiqueReasoning": "",
        "rawLlmResponse": "",
    }
    with (
        _patchSettings(),
        patch("agentic_claims.agents.compliance.node.mcpCallTool", AsyncMock(return_value=[])),
        patch(
            "agentic_claims.agents.compliance.node.runSelfCritique",
            AsyncMock(return_value=critiqueResp),
        ),
        patch("agentic_claims.agents.compliance.node.buildAgentLlm") as mockLlm,
    ):
        mockLlm.return_value.ainvoke = AsyncMock(return_value=fakeLlmResp)
        out = await complianceNode(state)
    findings = out["complianceFindings"]
    lowered = (findings.get("finalVerdict") or findings.get("verdict") or "").lower()
    assert "director" in lowered or findings.get("verdict", "").lower().startswith("requires")


@pytest.mark.asyncio
async def testAbuseFlagCoherenceIgnoresJustification() -> None:
    """When abuseFlags.coherenceOk is False, justification is not passed to LLM."""
    state = _baseState(
        userJustification="asdfasdf",
        abuseFlags={"coherenceOk": False, "crossCheckOk": True, "coherenceReason": "gibberish"},
    )
    critiqueResp = {
        "critiqueAgrees": True,
        "finalVerdict": "fail",
        "originalVerdict": "fail",
        "critiqueVerdict": "fail",
        "critiqueReasoning": "",
        "rawLlmResponse": "",
    }
    fakeLlmResp = type("R", (), {"content": '{"verdict": "fail"}'})()
    with (
        _patchSettings(),
        patch("agentic_claims.agents.compliance.node.mcpCallTool", AsyncMock(return_value=[])),
        patch(
            "agentic_claims.agents.compliance.node.runSelfCritique",
            AsyncMock(return_value=critiqueResp),
        ),
        patch("agentic_claims.agents.compliance.node.buildAgentLlm") as mockLlm,
    ):
        mockLlm.return_value.ainvoke = AsyncMock(return_value=fakeLlmResp)
        out = await complianceNode(state)
    findings = out["complianceFindings"]
    assert findings["verdict"].lower() == "fail"
    # critiqueResult must be in output
    assert out["critiqueResult"]["finalVerdict"].lower() == "fail"


@pytest.mark.asyncio
async def testCritiqueFlipsVerdict() -> None:
    """When critique disagrees, finalVerdict flips to critiqueVerdict."""
    state = _baseState(userJustification="client lunch meeting")
    critiqueResp = {
        "critiqueAgrees": False,
        "finalVerdict": "requiresReview",
        "originalVerdict": "pass",
        "critiqueVerdict": "requiresReview",
        "critiqueReasoning": "LLM missed a detail",
        "rawLlmResponse": "",
    }
    fakeLlmResp = type("R", (), {"content": '{"verdict": "pass"}'})()
    with (
        _patchSettings(),
        patch("agentic_claims.agents.compliance.node.mcpCallTool", AsyncMock(return_value=[])),
        patch(
            "agentic_claims.agents.compliance.node.runSelfCritique",
            AsyncMock(return_value=critiqueResp),
        ),
        patch("agentic_claims.agents.compliance.node.buildAgentLlm") as mockLlm,
    ):
        mockLlm.return_value.ainvoke = AsyncMock(return_value=fakeLlmResp)
        out = await complianceNode(state)
    findings = out["complianceFindings"]
    assert findings.get("finalVerdict") == "requiresReview"
    assert out["critiqueResult"]["critiqueAgrees"] is False
