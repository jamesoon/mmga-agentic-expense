# Author: jamesoon
"""Tests for Fraud Agent (Tool Call pattern) — Phase 3.

All tests mock MCP/LLM calls so they run locally without Docker or API keys.
These tests define the expected behavior BEFORE implementation (TDD red phase).
"""

from unittest.mock import AsyncMock, patch

import pytest
from langchain_core.messages import AIMessage, HumanMessage

from agentic_claims.agents.fraud.node import fraudNode
from agentic_claims.core.state import ClaimState


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

@pytest.fixture
def submittedClaimState() -> ClaimState:
    """A realistic state after intake submits a unique meal claim."""
    return {
        "claimId": "test-fraud-001",
        "status": "submitted",
        "messages": [
            HumanMessage(content="Here is my lunch receipt"),
            AIMessage(content="Claim submitted successfully"),
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


@pytest.fixture
def duplicateReceiptState(submittedClaimState) -> ClaimState:
    """Claim whose receipt matches an existing one in the DB."""
    state = dict(submittedClaimState)
    state["claimId"] = "test-fraud-duplicate"
    state["extractedReceipt"] = {
        "fields": {
            "merchant": "Starbucks Raffles",
            "date": "2026-03-15",
            "totalAmount": 12.80,
            "currency": "SGD",
            "category": "meals",
            "lineItems": [{"description": "Latte + Cake", "amount": 12.80}],
        },
        "confidence": {"merchant": 0.97, "totalAmount": 0.99},
    }
    return state


@pytest.fixture
def anomalousAmountState(submittedClaimState) -> ClaimState:
    """Claim with amount far above category average (5x)."""
    state = dict(submittedClaimState)
    state["claimId"] = "test-fraud-anomalous"
    state["extractedReceipt"] = {
        "fields": {
            "merchant": "Luxury Transport Co",
            "date": "2026-03-20",
            "totalAmount": 500.00,  # 5x above typical transport
            "currency": "SGD",
            "category": "transport",
            "lineItems": [{"description": "Private car", "amount": 500.00}],
        },
        "confidence": {"merchant": 0.95, "totalAmount": 0.99},
    }
    return state


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_fraudNodeReturnsFraudFindings(submittedClaimState):
    """Fraud node must return fraudFindings dict and messages."""
    result = await fraudNode(submittedClaimState)

    assert "messages" in result, "Must return messages"
    assert len(result["messages"]) > 0, "Must have at least one message"

    assert "fraudFindings" in result, "Must return fraudFindings"
    findings = result["fraudFindings"]
    assert "riskScore" in findings, "Findings must have 'riskScore' key"
    assert "duplicates" in findings, "Findings must have 'duplicates' key"
    assert "anomalies" in findings, "Findings must have 'anomalies' key"


@pytest.mark.asyncio
async def test_fraudDetectsDuplicateReceipt(duplicateReceiptState):
    """Same date + amount + vendor already in DB must be flagged as duplicate."""
    # Mock DB MCP to return an existing matching claim
    with patch(
        "agentic_claims.agents.fraud.node.mcpCallTool",
        new_callable=AsyncMock,
    ) as mockMcp:
        mockMcp.return_value = [
            {
                "claim_id": 42,
                "claim_number": "CLAIM-042",
                "merchant": "Starbucks Raffles",
                "receipt_date": "2026-03-15",
                "total_amount": 12.80,
                "employee_id": "EMP-001",
            }
        ]

        result = await fraudNode(duplicateReceiptState)

        findings = result["fraudFindings"]
        assert len(findings["duplicates"]) > 0, "Must detect duplicate receipt"
        assert findings["riskScore"] > 0.0, "Duplicate must increase risk score"


@pytest.mark.asyncio
async def test_fraudPassesUniqueReceipt(submittedClaimState):
    """No matching historical claims — clean fraud check."""
    # Mock DB MCP to return empty result (no duplicates)
    with patch(
        "agentic_claims.agents.fraud.node.mcpCallTool",
        new_callable=AsyncMock,
    ) as mockMcp:
        mockMcp.return_value = []  # No matching records

        result = await fraudNode(submittedClaimState)

        findings = result["fraudFindings"]
        assert findings["riskScore"] == 0.0, "Unique receipt should have zero risk"
        assert len(findings["duplicates"]) == 0, "Should have no duplicates"


@pytest.mark.asyncio
async def test_fraudQueriesDatabaseForDuplicates(submittedClaimState):
    """Fraud agent must call DB MCP server with executeQuery to check duplicates."""
    with patch(
        "agentic_claims.agents.fraud.node.mcpCallTool",
        new_callable=AsyncMock,
    ) as mockMcp:
        mockMcp.return_value = []

        await fraudNode(submittedClaimState)

        assert mockMcp.called, "Must call mcpCallTool for DB query"

        # Verify it was called with executeQuery tool
        callArgs = mockMcp.call_args_list
        toolNames = [
            call.args[1] if len(call.args) > 1 else call.kwargs.get("toolName", "")
            for call in callArgs
        ]
        assert any(
            "executeQuery" in name for name in toolNames
        ), "Must call executeQuery on DB MCP"


@pytest.mark.asyncio
async def test_fraudDetectsAnomalousAmount(anomalousAmountState):
    """Amount significantly above category average must flag anomaly."""
    # Mock DB MCP: no duplicates, but return avg amount for category
    with patch(
        "agentic_claims.agents.fraud.node.mcpCallTool",
        new_callable=AsyncMock,
    ) as mockMcp:
        # First call: duplicate check returns empty
        # Second call: category average query returns low average
        mockMcp.side_effect = [
            [],  # No duplicates
            [{"avg_amount": 40.00, "category": "transport"}],  # Category avg
        ]

        result = await fraudNode(anomalousAmountState)

        findings = result["fraudFindings"]
        assert len(findings["anomalies"]) > 0, "Must flag anomalous amount"
        assert findings["riskScore"] > 0.0, "Anomaly must increase risk score"


@pytest.mark.asyncio
async def test_fraudReturnsRiskScoreBetweenZeroAndOne(submittedClaimState):
    """Risk score must always be in the [0.0, 1.0] range."""
    with patch(
        "agentic_claims.agents.fraud.node.mcpCallTool",
        new_callable=AsyncMock,
    ) as mockMcp:
        mockMcp.return_value = []

        result = await fraudNode(submittedClaimState)

        score = result["fraudFindings"]["riskScore"]
        assert isinstance(score, (int, float)), "Risk score must be numeric"
        assert 0.0 <= score <= 1.0, f"Risk score {score} must be in [0.0, 1.0]"
