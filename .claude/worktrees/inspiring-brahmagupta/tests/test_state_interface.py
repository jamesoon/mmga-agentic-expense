# Author: jamesoon
"""Tests for state interface contracts between intake and post-submission agents.

Validates that the output of one agent matches the input expectations of the next.
These are structural/contract tests — they verify data shapes, not business logic.
"""

from unittest.mock import AsyncMock, patch

import pytest
from langchain_core.messages import AIMessage, HumanMessage

from agentic_claims.core.graph import buildGraph
from agentic_claims.core.state import ClaimState


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

@pytest.fixture
def intakeOutputState() -> ClaimState:
    """Realistic state after intake agent completes and submits a claim."""
    return {
        "claimId": "test-interface-001",
        "status": "submitted",
        "messages": [
            HumanMessage(content="Here is my lunch receipt"),
            AIMessage(content="Claim CLAIM-001 submitted successfully"),
        ],
        "extractedReceipt": {
            "fields": {
                "merchant": "McDonald's Orchard",
                "date": "2026-03-20",
                "totalAmount": 18.50,
                "currency": "SGD",
                "category": "meals",
                "lineItems": [
                    {"description": "Big Mac Meal", "amount": 12.50},
                    {"description": "McFlurry", "amount": 6.00},
                ],
            },
            "confidence": {"merchant": 0.98, "date": 0.97, "totalAmount": 0.99},
        },
        "violations": [],
        "currencyConversion": None,
        "claimSubmitted": True,
        "intakeFindings": {"mismatches": [], "overrides": [], "redFlags": []},
    }


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------

def test_intakeOutputHasRequiredFieldsForPostSubmission(intakeOutputState):
    """Intake output must contain fields that compliance and fraud agents need."""
    # These are the fields post-submission agents read from state
    assert "extractedReceipt" in intakeOutputState, "Must have extractedReceipt"
    assert intakeOutputState["extractedReceipt"] is not None, "extractedReceipt must not be None"

    assert "claimSubmitted" in intakeOutputState, "Must have claimSubmitted flag"
    assert intakeOutputState["claimSubmitted"] is True, "claimSubmitted must be True"

    assert "claimId" in intakeOutputState, "Must have claimId"
    assert "status" in intakeOutputState, "Must have status"

    # extractedReceipt must have the fields sub-dict
    receipt = intakeOutputState["extractedReceipt"]
    assert "fields" in receipt, "extractedReceipt must have 'fields'"
    fields = receipt["fields"]
    assert "merchant" in fields, "Receipt must have merchant"
    assert "date" in fields, "Receipt must have date"
    assert "totalAmount" in fields, "Receipt must have totalAmount"
    assert "currency" in fields, "Receipt must have currency"


def test_complianceFindingsStructure():
    """Compliance findings must have the expected structure for advisor consumption."""
    # This is the contract the compliance node must output
    expectedFindings = {
        "pass": True,
        "violations": [],
        "citedClauses": [],
    }

    assert "pass" in expectedFindings, "Must have 'pass' boolean"
    assert isinstance(expectedFindings["pass"], bool), "'pass' must be boolean"
    assert "violations" in expectedFindings, "Must have 'violations' list"
    assert isinstance(expectedFindings["violations"], list), "'violations' must be list"
    assert "citedClauses" in expectedFindings, "Must have 'citedClauses' list"
    assert isinstance(expectedFindings["citedClauses"], list), "'citedClauses' must be list"

    # Test with violations present
    findingsWithViolation = {
        "pass": False,
        "violations": [
            {"description": "Over budget", "severity": "high"},
        ],
        "citedClauses": [
            {"policy": "meals.md", "section": "Section 2", "clause": "Daily cap SGD 50"},
        ],
    }
    for violation in findingsWithViolation["violations"]:
        assert "description" in violation, "Each violation must have description"
    for clause in findingsWithViolation["citedClauses"]:
        assert "policy" in clause, "Each clause must have policy"
        assert "section" in clause, "Each clause must have section"
        assert "clause" in clause, "Each clause must have clause text"


def test_fraudFindingsStructure():
    """Fraud findings must have the expected structure for advisor consumption."""
    expectedFindings = {
        "riskScore": 0.0,
        "duplicates": [],
        "anomalies": [],
    }

    assert "riskScore" in expectedFindings, "Must have 'riskScore'"
    assert isinstance(expectedFindings["riskScore"], (int, float)), "'riskScore' must be numeric"
    assert 0.0 <= expectedFindings["riskScore"] <= 1.0, "riskScore must be in [0, 1]"
    assert "duplicates" in expectedFindings, "Must have 'duplicates' list"
    assert isinstance(expectedFindings["duplicates"], list), "'duplicates' must be list"
    assert "anomalies" in expectedFindings, "Must have 'anomalies' list"
    assert isinstance(expectedFindings["anomalies"], list), "'anomalies' must be list"


def test_advisorDecisionStructure():
    """Advisor decision must have the expected structure."""
    expectedDecision = {
        "action": "approve",
        "reasoning": "All checks passed. No violations or fraud flags detected.",
    }

    assert "action" in expectedDecision, "Must have 'action'"
    assert expectedDecision["action"] in ("approve", "return", "escalate"), (
        "Action must be one of: approve, return, escalate"
    )
    assert "reasoning" in expectedDecision, "Must have 'reasoning'"
    assert isinstance(expectedDecision["reasoning"], str), "'reasoning' must be string"
    assert len(expectedDecision["reasoning"]) > 0, "'reasoning' must not be empty"


@pytest.mark.asyncio
async def test_parallelFanOutPreservesState(intakeOutputState):
    """Both compliance and fraud receive the same extractedReceipt from state."""
    receivedStates = {}

    async def mockComplianceNode(state: ClaimState) -> dict:
        receivedStates["compliance"] = state.get("extractedReceipt")
        return {"messages": [AIMessage(content="Compliance done")]}

    async def mockFraudNode(state: ClaimState) -> dict:
        receivedStates["fraud"] = state.get("extractedReceipt")
        return {"messages": [AIMessage(content="Fraud done")]}

    async def mockIntakeNode(state: ClaimState) -> dict:
        return {
            "messages": [AIMessage(content="Intake done")],
            "claimSubmitted": True,
            "extractedReceipt": intakeOutputState["extractedReceipt"],
        }

    async def mockAdvisorNode(state: ClaimState) -> dict:
        return {"messages": [AIMessage(content="Advisor done")], "status": "approved"}

    with (
        patch("agentic_claims.core.graph.intakeNode", mockIntakeNode),
        patch("agentic_claims.core.graph.complianceNode", mockComplianceNode),
        patch("agentic_claims.core.graph.fraudNode", mockFraudNode),
        patch("agentic_claims.core.graph.advisorNode", mockAdvisorNode),
    ):
        graph = buildGraph().compile()
        await graph.ainvoke(intakeOutputState)

    # Both agents must have received the same extractedReceipt
    assert receivedStates.get("compliance") is not None, "Compliance must receive extractedReceipt"
    assert receivedStates.get("fraud") is not None, "Fraud must receive extractedReceipt"
    assert receivedStates["compliance"] == receivedStates["fraud"], (
        "Both agents must receive identical extractedReceipt"
    )


@pytest.mark.asyncio
async def test_advisorReceivesBothFindings(intakeOutputState):
    """After parallel fan-out, advisor state must contain both findings."""
    receivedState = {}

    async def mockIntakeNode(state: ClaimState) -> dict:
        return {
            "messages": [AIMessage(content="Intake done")],
            "claimSubmitted": True,
        }

    async def mockComplianceNode(state: ClaimState) -> dict:
        return {
            "messages": [AIMessage(content="Compliance done")],
            "complianceFindings": {"pass": True, "violations": [], "citedClauses": []},
        }

    async def mockFraudNode(state: ClaimState) -> dict:
        return {
            "messages": [AIMessage(content="Fraud done")],
            "fraudFindings": {"riskScore": 0.0, "duplicates": [], "anomalies": []},
        }

    async def mockAdvisorNode(state: ClaimState) -> dict:
        receivedState["complianceFindings"] = state.get("complianceFindings")
        receivedState["fraudFindings"] = state.get("fraudFindings")
        return {"messages": [AIMessage(content="Advisor done")], "status": "approved"}

    with (
        patch("agentic_claims.core.graph.intakeNode", mockIntakeNode),
        patch("agentic_claims.core.graph.complianceNode", mockComplianceNode),
        patch("agentic_claims.core.graph.fraudNode", mockFraudNode),
        patch("agentic_claims.core.graph.advisorNode", mockAdvisorNode),
    ):
        graph = buildGraph().compile()
        await graph.ainvoke(intakeOutputState)

    assert receivedState.get("complianceFindings") is not None, (
        "Advisor must receive complianceFindings"
    )
    assert receivedState.get("fraudFindings") is not None, (
        "Advisor must receive fraudFindings"
    )
    assert receivedState["complianceFindings"]["pass"] is True
    assert receivedState["fraudFindings"]["riskScore"] == 0.0
