# Author: jamesoon
"""Compliance agent node — Evaluator pattern.

Validates submitted claims against SUTD expense policy rules.
Deterministic checks: budget caps, submission deadline, approval thresholds.
RAG-augmented with policy clause citations via MCP RAG server.
"""

import logging
from datetime import datetime, timezone

from langchain_core.messages import AIMessage

from agentic_claims.agents.intake.utils.mcpClient import mcpCallTool
from agentic_claims.core.config import getSettings
from agentic_claims.core.state import ClaimState

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Policy constants (sourced from policy markdown files)
# ---------------------------------------------------------------------------

MEAL_DAILY_CAP = 50.00  # SGD per day — meals.md Section 2
MEAL_OVERSEAS_MULTIPLIER = 1.5  # meals.md Section 4

SUBMISSION_DEADLINE_DAYS = 30  # calendar days — general.md Section 1

APPROVAL_THRESHOLD_AUTO = 200.0  # SGD — general.md Section 3
APPROVAL_THRESHOLD_MANAGER = 1000.0  # SGD — general.md Section 3


async def complianceNode(state: ClaimState) -> dict:
    """Check claim compliance with company policies.

    Runs deterministic rule checks against extracted receipt data,
    then augments with RAG policy search for cited clauses.

    Args:
        state: Current claim state with extractedReceipt

    Returns:
        Partial state update with complianceFindings and messages
    """
    violations: list[dict] = []
    citedClauses: list[dict] = []

    # Extract receipt fields
    extractedReceipt = state.get("extractedReceipt") or {}
    fields = extractedReceipt.get("fields", {})
    totalAmount = fields.get("totalAmount", 0.0)
    currency = fields.get("currency", "SGD")
    category = fields.get("category", "").lower()
    receiptDate = fields.get("date", "")

    # --- Check 1: Budget cap (meals) ---
    if category == "meals" and totalAmount > MEAL_DAILY_CAP:
        violations.append({
            "description": f"Meal total SGD {totalAmount:.2f} exceeds daily cap of SGD {MEAL_DAILY_CAP:.2f}",
            "severity": "high",
        })
        citedClauses.append({
            "policy": "meals.md",
            "section": "Section 2",
            "clause": "Daily meal cap is SGD 50 per day",
        })

    # --- Check 2: Submission deadline (30 days) ---
    if receiptDate:
        try:
            receiptDt = datetime.strptime(receiptDate, "%Y-%m-%d").replace(
                tzinfo=timezone.utc
            )
            elapsed = (datetime.now(timezone.utc) - receiptDt).days
            if elapsed > SUBMISSION_DEADLINE_DAYS:
                violations.append({
                    "description": (
                        f"Receipt is {elapsed} days old, "
                        f"exceeds 30-day submission deadline"
                    ),
                    "severity": "high",
                })
                citedClauses.append({
                    "policy": "general.md",
                    "section": "Section 1",
                    "clause": "Hard deadline of 30 calendar days from expense incurrence",
                })
        except ValueError:
            logger.warning("Could not parse receipt date: %s", receiptDate)

    # --- Check 3: Approval threshold ---
    if totalAmount > APPROVAL_THRESHOLD_MANAGER:
        citedClauses.append({
            "policy": "general.md",
            "section": "Section 3",
            "clause": "Claims above SGD 1000 require dept head approval",
        })

    # --- RAG policy search for additional context ---
    try:
        settings = getSettings()
        ragMcpUrl = settings.rag_mcp_url
    except Exception:
        ragMcpUrl = "http://localhost:8001/mcp/"

    try:
        queryText = f"{category} expense SGD {totalAmount}"
        ragResults = await mcpCallTool(
            ragMcpUrl,
            "searchPolicies",
            {"query": queryText, "limit": 3},
        )
        if isinstance(ragResults, list):
            for chunk in ragResults:
                if isinstance(chunk, dict) and "text" in chunk:
                    citedClauses.append({
                        "policy": chunk.get("file", "unknown"),
                        "section": chunk.get("section", "unknown"),
                        "clause": chunk.get("text", ""),
                    })
    except Exception as e:
        logger.warning("RAG policy search failed (non-fatal): %s", e)

    # --- Build findings ---
    compliancePassed = len(violations) == 0

    findings = {
        "pass": compliancePassed,
        "violations": violations,
        "citedClauses": citedClauses,
    }

    # Summary message
    if compliancePassed:
        summary = f"Compliance check PASSED for {category} claim of SGD {totalAmount:.2f}."
    else:
        violationSummary = "; ".join(v["description"] for v in violations)
        summary = f"Compliance check FAILED: {violationSummary}"

    return {
        "complianceFindings": findings,
        "messages": [AIMessage(content=summary)],
    }
