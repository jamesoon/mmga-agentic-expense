# Author: jamesoon
"""Advisor agent node — Reflection + Routing pattern.

Synthesizes compliance and fraud findings into a final decision.
Routes claims to: auto-approve, return-to-claimant, or escalate-to-reviewer.
Updates claim status in DB and sends email notifications.
"""

import logging

from langchain_core.messages import AIMessage

from agentic_claims.agents.intake.utils.mcpClient import mcpCallTool
from agentic_claims.core.config import getSettings
from agentic_claims.core.state import ClaimState

logger = logging.getLogger(__name__)

# Decision thresholds
FRAUD_RISK_ESCALATE_THRESHOLD = 0.3  # Escalate if riskScore >= this


async def advisorNode(state: ClaimState) -> dict:
    """Make final decision on claim approval or rejection.

    Decision matrix:
    - Clean (compliance pass + low fraud) → auto-approve
    - Violations (compliance fail + low fraud) → return to claimant
    - Suspicious (high fraud or disagreement) → escalate to reviewer

    Args:
        state: Current claim state with complianceFindings and fraudFindings

    Returns:
        Partial state update with advisorDecision, status, and messages
    """
    claimId = state.get("claimId", "unknown")

    # Read findings from parallel agents
    complianceFindings = state.get("complianceFindings") or {
        "pass": True, "violations": [], "citedClauses": []
    }
    fraudFindings = state.get("fraudFindings") or {
        "riskScore": 0.0, "duplicates": [], "anomalies": []
    }

    compliancePassed = complianceFindings.get("pass", True)
    violations = complianceFindings.get("violations", [])
    citedClauses = complianceFindings.get("citedClauses", [])
    riskScore = fraudFindings.get("riskScore", 0.0)
    duplicates = fraudFindings.get("duplicates", [])
    anomalies = fraudFindings.get("anomalies", [])

    # --- REFLECT: Synthesize findings ---
    hasFraudFlags = (
        riskScore >= FRAUD_RISK_ESCALATE_THRESHOLD
        or len(duplicates) > 0
        or len(anomalies) > 0
    )

    # --- ROUTE: Decision matrix ---
    if hasFraudFlags:
        # Any fraud concern → escalate (conservative approach)
        action = "escalate"
        status = "escalated"
        reasoning = _buildEscalateReasoning(
            riskScore, duplicates, anomalies, compliancePassed, violations
        )
    elif not compliancePassed:
        # Compliance violations only → return to claimant
        action = "return"
        status = "returned"
        reasoning = _buildReturnReasoning(violations, citedClauses)
    else:
        # Clean claim → auto-approve
        action = "approve"
        status = "approved"
        reasoning = "All compliance checks passed. No fraud flags detected. Claim auto-approved."

    # --- MCP: Update claim status in DB ---
    try:
        settings = getSettings()
        dbMcpUrl = settings.db_mcp_url
    except Exception:
        dbMcpUrl = "http://localhost:8002/mcp/"

    try:
        claimIdInt = int(claimId) if claimId.isdigit() else 0
        await mcpCallTool(
            dbMcpUrl,
            "updateClaimStatus",
            {"claimId": claimIdInt, "newStatus": status, "actor": "advisor-agent"},
        )
    except Exception as e:
        logger.warning("Failed to update claim status (non-fatal): %s", e)

    # --- MCP: Send email notification ---
    try:
        settings = getSettings()
        emailMcpUrl = settings.email_mcp_url
    except Exception:
        emailMcpUrl = "http://localhost:8004/mcp/"

    try:
        await mcpCallTool(
            emailMcpUrl,
            "sendClaimNotification",
            {
                "to": "claims@sutd.edu.sg",
                "claimNumber": claimId,
                "status": status,
                "message": reasoning,
            },
        )
    except Exception as e:
        logger.warning("Failed to send email notification (non-fatal): %s", e)

    # Summary message
    summary = f"Advisor decision: {action.upper()} — {reasoning}"

    return {
        "advisorDecision": {"action": action, "reasoning": reasoning},
        "status": status,
        "messages": [AIMessage(content=summary)],
    }


def _buildReturnReasoning(violations: list[dict], citedClauses: list[dict]) -> str:
    """Build reasoning string for return-to-claimant decisions."""
    parts = []
    for v in violations:
        parts.append(v.get("description", "Policy violation detected"))
    for c in citedClauses:
        policy = c.get("policy", "")
        section = c.get("section", "")
        clause = c.get("clause", "")
        if policy or section:
            parts.append(f"Policy reference: {policy} {section} — {clause}")
    return "Claim returned due to compliance violation. " + "; ".join(parts)


def _buildEscalateReasoning(
    riskScore: float,
    duplicates: list[dict],
    anomalies: list[dict],
    compliancePassed: bool,
    violations: list[dict],
) -> str:
    """Build reasoning string for escalation decisions."""
    parts = [f"Risk score: {riskScore:.2f}"]
    if duplicates:
        parts.append(f"{len(duplicates)} potential duplicate(s) found")
    if anomalies:
        for a in anomalies:
            parts.append(a.get("description", "Anomalous pattern detected"))
    if not compliancePassed:
        for v in violations:
            parts.append(v.get("description", "Compliance violation"))
    return "Claim escalated for human review. " + "; ".join(parts)
