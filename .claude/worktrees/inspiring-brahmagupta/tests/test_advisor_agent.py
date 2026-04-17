# Author: jamesoon
"""Tests for Advisor Agent (Reflection + Routing pattern) — Phase 4.

All tests mock MCP/LLM calls so they run locally without Docker or API keys.
These tests define the expected behavior BEFORE implementation (TDD red phase).
"""

from unittest.mock import AsyncMock, patch

import pytest
from langchain_core.messages import AIMessage, HumanMessage

from agentic_claims.agents.advisor.node import advisorNode
from agentic_claims.core.state import ClaimState


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

@pytest.fixture
def cleanClaimState() -> ClaimState:
    """A claim that passed compliance and has no fraud flags."""
    return {
        "claimId": "test-advisor-clean",
        "status": "submitted",
        "messages": [
            HumanMessage(content="Here is my lunch receipt"),
            AIMessage(content="Claim submitted successfully"),
            AIMessage(content="Compliance: all checks passed"),
            AIMessage(content="Fraud: no duplicates found"),
        ],
        "extractedReceipt": {
            "fields": {
                "merchant": "McDonald's Orchard",
                "date": "2026-03-20",
                "totalAmount": 18.50,
                "currency": "SGD",
                "category": "meals",
            },
        },
        "complianceFindings": {
            "pass": True,
            "violations": [],
            "citedClauses": [],
        },
        "fraudFindings": {
            "riskScore": 0.0,
            "duplicates": [],
            "anomalies": [],
        },
        "claimSubmitted": True,
    }


@pytest.fixture
def violationClaimState(cleanClaimState) -> ClaimState:
    """A claim that failed compliance but has low fraud risk."""
    state = dict(cleanClaimState)
    state["claimId"] = "test-advisor-violation"
    state["complianceFindings"] = {
        "pass": False,
        "violations": [
            {
                "description": "Meal total SGD 80 exceeds daily cap of SGD 50",
                "severity": "high",
            }
        ],
        "citedClauses": [
            {
                "policy": "meals.md",
                "section": "Section 2",
                "clause": "Daily meal cap is SGD 50 per day",
            }
        ],
    }
    state["fraudFindings"] = {
        "riskScore": 0.1,
        "duplicates": [],
        "anomalies": [],
    }
    return state


@pytest.fixture
def suspiciousClaimState(cleanClaimState) -> ClaimState:
    """A claim with high fraud risk — duplicate detected."""
    state = dict(cleanClaimState)
    state["claimId"] = "test-advisor-suspicious"
    state["complianceFindings"] = {
        "pass": True,
        "violations": [],
        "citedClauses": [],
    }
    state["fraudFindings"] = {
        "riskScore": 0.85,
        "duplicates": [
            {
                "claimNumber": "CLAIM-042",
                "merchant": "McDonald's Orchard",
                "date": "2026-03-20",
                "amount": 18.50,
            }
        ],
        "anomalies": [],
    }
    return state


@pytest.fixture
def disagreementClaimState(cleanClaimState) -> ClaimState:
    """Compliance passes but fraud flags — agents disagree."""
    state = dict(cleanClaimState)
    state["claimId"] = "test-advisor-disagreement"
    state["complianceFindings"] = {
        "pass": True,
        "violations": [],
        "citedClauses": [],
    }
    state["fraudFindings"] = {
        "riskScore": 0.6,
        "duplicates": [],
        "anomalies": [
            {
                "description": "Amount 5x above transport category average",
                "severity": "medium",
            }
        ],
    }
    return state


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_advisorNodeReturnsDecision(cleanClaimState):
    """Advisor node must return advisorDecision, status, and messages."""
    result = await advisorNode(cleanClaimState)

    assert "messages" in result, "Must return messages"
    assert len(result["messages"]) > 0, "Must have at least one message"

    assert "advisorDecision" in result, "Must return advisorDecision"
    decision = result["advisorDecision"]
    assert "action" in decision, "Decision must have 'action' key"
    assert "reasoning" in decision, "Decision must have 'reasoning' key"
    assert decision["action"] in ("approve", "return", "escalate"), (
        f"Action must be approve/return/escalate, got: {decision['action']}"
    )

    assert "status" in result, "Must return status"
    assert result["status"] in ("approved", "returned", "escalated"), (
        f"Status must be approved/returned/escalated, got: {result['status']}"
    )


@pytest.mark.asyncio
async def test_advisorAutoApprovesCleanClaim(cleanClaimState):
    """No violations + low fraud risk = auto-approve."""
    result = await advisorNode(cleanClaimState)

    assert result["status"] == "approved", "Clean claim must be approved"
    assert result["advisorDecision"]["action"] == "approve"


@pytest.mark.asyncio
async def test_advisorReturnsClaimWithViolations(violationClaimState):
    """Compliance violations + low fraud = return to claimant."""
    result = await advisorNode(violationClaimState)

    assert result["status"] == "returned", "Violation claim must be returned"
    assert result["advisorDecision"]["action"] == "return"

    # Reasoning should reference the violation
    reasoning = result["advisorDecision"]["reasoning"].lower()
    assert "violation" in reasoning or "exceed" in reasoning or "cap" in reasoning, (
        "Reasoning should reference the compliance violation"
    )


@pytest.mark.asyncio
async def test_advisorEscalatesSuspiciousClaim(suspiciousClaimState):
    """High fraud risk = escalate to reviewer."""
    result = await advisorNode(suspiciousClaimState)

    assert result["status"] == "escalated", "Suspicious claim must be escalated"
    assert result["advisorDecision"]["action"] == "escalate"


@pytest.mark.asyncio
async def test_advisorEscalatesOnDisagreement(disagreementClaimState):
    """Compliance pass + fraud flags = conservative escalation."""
    result = await advisorNode(disagreementClaimState)

    assert result["status"] == "escalated", "Disagreement must be escalated (conservative)"
    assert result["advisorDecision"]["action"] == "escalate"


@pytest.mark.asyncio
async def test_advisorUpdatesClaimStatusInDb(cleanClaimState):
    """Advisor must call updateClaimStatus via DB MCP server."""
    with patch(
        "agentic_claims.agents.advisor.node.mcpCallTool",
        new_callable=AsyncMock,
    ) as mockMcp:
        mockMcp.return_value = {"claim_id": 1, "status": "approved"}

        await advisorNode(cleanClaimState)

        assert mockMcp.called, "Must call mcpCallTool"

        # Find the updateClaimStatus call
        callArgs = mockMcp.call_args_list
        toolNames = [
            call.args[1] if len(call.args) > 1 else call.kwargs.get("toolName", "")
            for call in callArgs
        ]
        assert any(
            "updateClaimStatus" in name for name in toolNames
        ), "Must call updateClaimStatus on DB MCP"


@pytest.mark.asyncio
async def test_advisorSendsEmailNotification(violationClaimState):
    """Advisor must send email notification when returning a claim."""
    with patch(
        "agentic_claims.agents.advisor.node.mcpCallTool",
        new_callable=AsyncMock,
    ) as mockMcp:
        mockMcp.return_value = {"success": True}

        await advisorNode(violationClaimState)

        assert mockMcp.called, "Must call mcpCallTool"

        # Find the sendClaimNotification call
        callArgs = mockMcp.call_args_list
        toolNames = [
            call.args[1] if len(call.args) > 1 else call.kwargs.get("toolName", "")
            for call in callArgs
        ]
        assert any(
            "sendClaimNotification" in name or "sendEmail" in name
            for name in toolNames
        ), "Must call sendClaimNotification or sendEmail on Email MCP"


@pytest.mark.asyncio
async def test_advisorCitesPolicyClauses(violationClaimState):
    """Return decision must include specific policy references from compliance."""
    result = await advisorNode(violationClaimState)

    # The advisor's message or decision reasoning should cite the policy
    reasoning = result["advisorDecision"]["reasoning"].lower()
    messages = [msg.content.lower() for msg in result["messages"]]
    allText = reasoning + " ".join(messages)

    assert "meals" in allText or "section" in allText or "policy" in allText, (
        "Return decision must cite the relevant policy"
    )
