# Author: jamesoon
"""Tests for Compliance Agent (Evaluator pattern) — Phase 3.

All tests mock MCP/LLM calls so they run locally without Docker or API keys.
These tests define the expected behavior BEFORE implementation (TDD red phase).
"""

from unittest.mock import AsyncMock, patch

import pytest
from langchain_core.messages import AIMessage, HumanMessage

from agentic_claims.agents.compliance.node import complianceNode
from agentic_claims.core.state import ClaimState


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

@pytest.fixture
def submittedClaimState() -> ClaimState:
    """A realistic state after intake submits a clean meal claim."""
    return {
        "claimId": "test-compliance-001",
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
def overBudgetMealState(submittedClaimState) -> ClaimState:
    """Meal claim of SGD 80 — exceeds daily cap of SGD 50."""
    state = dict(submittedClaimState)
    state["claimId"] = "test-compliance-overbudget"
    state["extractedReceipt"] = {
        "fields": {
            "merchant": "Fine Dining Restaurant",
            "date": "2026-03-20",
            "totalAmount": 80.00,
            "currency": "SGD",
            "category": "meals",
            "lineItems": [
                {"description": "Wagyu Steak", "amount": 65.00},
                {"description": "Dessert", "amount": 15.00},
            ],
        },
        "confidence": {"merchant": 0.95, "totalAmount": 0.99},
    }
    return state


@pytest.fixture
def expiredReceiptState(submittedClaimState) -> ClaimState:
    """Receipt older than 30 days — violates general.md Section 1."""
    state = dict(submittedClaimState)
    state["claimId"] = "test-compliance-expired"
    state["extractedReceipt"] = {
        "fields": {
            "merchant": "7-Eleven",
            "date": "2026-01-15",  # >30 days from "now"
            "totalAmount": 5.00,
            "currency": "SGD",
            "category": "meals",
            "lineItems": [],
        },
        "confidence": {"merchant": 0.90, "totalAmount": 0.95},
    }
    return state


@pytest.fixture
def highValueClaimState(submittedClaimState) -> ClaimState:
    """Claim > SGD 1000 — requires dept head approval per general.md Section 3."""
    state = dict(submittedClaimState)
    state["claimId"] = "test-compliance-highvalue"
    state["extractedReceipt"] = {
        "fields": {
            "merchant": "Hilton Singapore",
            "date": "2026-03-20",
            "totalAmount": 1500.00,
            "currency": "SGD",
            "category": "accommodation",
            "lineItems": [{"description": "3 nights", "amount": 1500.00}],
        },
        "confidence": {"merchant": 0.99, "totalAmount": 0.99},
    }
    return state


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_complianceNodeReturnsComplianceFindings(submittedClaimState):
    """Compliance node must return complianceFindings dict and messages."""
    result = await complianceNode(submittedClaimState)

    assert "messages" in result, "Must return messages"
    assert len(result["messages"]) > 0, "Must have at least one message"

    assert "complianceFindings" in result, "Must return complianceFindings"
    findings = result["complianceFindings"]
    assert "pass" in findings, "Findings must have 'pass' key"
    assert "violations" in findings, "Findings must have 'violations' key"
    assert "citedClauses" in findings, "Findings must have 'citedClauses' key"


@pytest.mark.asyncio
async def test_complianceDetectsOverBudgetMeal(overBudgetMealState):
    """SGD 80 meal exceeds daily cap of SGD 50 — must flag violation."""
    result = await complianceNode(overBudgetMealState)

    findings = result["complianceFindings"]
    assert findings["pass"] is False, "Over-budget claim must fail compliance"
    assert len(findings["violations"]) > 0, "Must have at least one violation"

    # Check that the violation mentions the amount or budget cap
    violationTexts = [v.get("description", "") for v in findings["violations"]]
    allText = " ".join(violationTexts).lower()
    assert "50" in allText or "cap" in allText or "exceed" in allText, (
        "Violation should reference the budget cap or exceeded amount"
    )


@pytest.mark.asyncio
async def test_compliancePassesCleanClaim(submittedClaimState):
    """SGD 18.50 meal is within limits — must pass compliance."""
    result = await complianceNode(submittedClaimState)

    findings = result["complianceFindings"]
    assert findings["pass"] is True, "Clean claim must pass compliance"
    assert len(findings["violations"]) == 0, "Clean claim must have no violations"


@pytest.mark.asyncio
async def test_complianceDetectsExpiredSubmission(expiredReceiptState):
    """Receipt >30 days old violates general.md Section 1 submission deadline."""
    result = await complianceNode(expiredReceiptState)

    findings = result["complianceFindings"]
    assert findings["pass"] is False, "Expired receipt must fail compliance"
    assert len(findings["violations"]) > 0, "Must flag expired submission"

    # Check that violation cites the deadline policy
    violationTexts = [v.get("description", "") for v in findings["violations"]]
    allText = " ".join(violationTexts).lower()
    assert "30" in allText or "deadline" in allText or "expired" in allText, (
        "Violation should reference the 30-day submission deadline"
    )


@pytest.mark.asyncio
async def test_complianceChecksApprovalThreshold(highValueClaimState):
    """Claim >SGD 1000 requires dept head approval per general.md Section 3."""
    result = await complianceNode(highValueClaimState)

    findings = result["complianceFindings"]
    # The claim isn't necessarily a "fail" — it's a flag for approval routing
    # Check that cited clauses mention the threshold
    allClauses = findings.get("citedClauses", [])
    allClauseText = " ".join(
        [c.get("clause", "") + c.get("section", "") for c in allClauses]
    ).lower()
    assert "1000" in allClauseText or "dept head" in allClauseText or "approval" in allClauseText, (
        "Must cite the approval threshold policy clause"
    )


@pytest.mark.asyncio
async def test_complianceSearchesPoliciesViaRag(submittedClaimState):
    """Compliance agent must call the RAG MCP server to search policies."""
    # We patch wherever the compliance node imports mcpCallTool
    with patch(
        "agentic_claims.agents.compliance.node.mcpCallTool",
        new_callable=AsyncMock,
    ) as mockMcp:
        mockMcp.return_value = [
            {
                "text": "Daily meal cap is SGD 50 per day.",
                "file": "meals.md",
                "category": "meals",
                "section": "Section 2",
                "score": 0.92,
            }
        ]

        await complianceNode(submittedClaimState)

        # Verify MCP was called at least once
        assert mockMcp.called, "Must call mcpCallTool for policy search"

        # Verify it was called with the RAG server (searchPolicies tool)
        callArgs = mockMcp.call_args_list
        toolNames = [call.args[1] if len(call.args) > 1 else call.kwargs.get("toolName", "") for call in callArgs]
        assert any(
            "searchPolicies" in name or "getPolicyByCategory" in name
            for name in toolNames
        ), "Must call searchPolicies or getPolicyByCategory on RAG MCP"


@pytest.mark.asyncio
async def test_complianceCitesSpecificPolicyClauses(overBudgetMealState):
    """Each violation must include specific policy references."""
    result = await complianceNode(overBudgetMealState)

    findings = result["complianceFindings"]
    citedClauses = findings.get("citedClauses", [])

    assert len(citedClauses) > 0, "Must cite at least one policy clause"
    for clause in citedClauses:
        assert "policy" in clause, "Each cited clause must name the policy file"
        assert "section" in clause, "Each cited clause must name the section"
        assert "clause" in clause, "Each cited clause must include the clause text"
