# Author: jamesoon
"""Fraud detection agent node — Tool Call pattern.

Detects duplicate receipts and anomalous amounts by querying the
claims database via the DB MCP server.
"""

import logging

from langchain_core.messages import AIMessage

from agentic_claims.agents.intake.utils.mcpClient import mcpCallTool
from agentic_claims.core.config import getSettings
from agentic_claims.core.state import ClaimState

logger = logging.getLogger(__name__)

# Risk score weights
DUPLICATE_RISK = 0.9
ANOMALY_RISK = 0.5
ANOMALY_MULTIPLIER = 3.0  # Flag if amount > avg * this


async def fraudNode(state: ClaimState) -> dict:
    """Detect potential fraud in expense claims.

    Two-step detection:
    1. Duplicate check — query DB for matching merchant + date + amount
    2. Anomaly check — compare amount against category average

    Args:
        state: Current claim state with extractedReceipt

    Returns:
        Partial state update with fraudFindings and messages
    """
    duplicates: list[dict] = []
    anomalies: list[dict] = []
    riskScore = 0.0

    # Extract receipt fields
    extractedReceipt = state.get("extractedReceipt") or {}
    fields = extractedReceipt.get("fields", {})
    merchant = fields.get("merchant", "")
    receiptDate = fields.get("date", "")
    totalAmount = fields.get("totalAmount", 0.0)
    category = fields.get("category", "").lower()
    claimId = state.get("claimId", "")

    # Resolve MCP URL
    try:
        settings = getSettings()
        dbMcpUrl = settings.db_mcp_url
    except Exception:
        dbMcpUrl = "http://localhost:8002/mcp/"

    # --- Check 1: Duplicate receipts ---
    try:
        duplicateQuery = (
            f"SELECT c.id AS claim_id, c.claim_number, r.merchant, "
            f"r.receipt_date, r.total_amount, c.employee_id "
            f"FROM receipts r JOIN claims c ON r.claim_id = c.id "
            f"WHERE r.merchant = '{merchant}' "
            f"AND r.receipt_date = '{receiptDate}' "
            f"AND r.total_amount = {totalAmount}"
        )
        dupResults = await mcpCallTool(
            dbMcpUrl, "executeQuery", {"query": duplicateQuery}
        )
        if isinstance(dupResults, list) and len(dupResults) > 0:
            for row in dupResults:
                duplicates.append({
                    "claimNumber": row.get("claim_number", "unknown"),
                    "merchant": row.get("merchant", merchant),
                    "date": str(row.get("receipt_date", receiptDate)),
                    "amount": row.get("total_amount", totalAmount),
                })
            riskScore += DUPLICATE_RISK
    except Exception as e:
        logger.warning("Duplicate check failed (non-fatal): %s", e)

    # --- Check 2: Anomalous amount ---
    try:
        avgQuery = (
            f"SELECT AVG(r.total_amount) AS avg_amount, "
            f"'{category}' AS category "
            f"FROM receipts r JOIN claims c ON r.claim_id = c.id"
        )
        avgResults = await mcpCallTool(
            dbMcpUrl, "executeQuery", {"query": avgQuery}
        )
        if isinstance(avgResults, list) and len(avgResults) > 0:
            avgAmount = avgResults[0].get("avg_amount")
            if avgAmount and avgAmount > 0 and totalAmount > avgAmount * ANOMALY_MULTIPLIER:
                anomalies.append({
                    "description": (
                        f"Amount SGD {totalAmount:.2f} is "
                        f"{totalAmount / avgAmount:.1f}x above "
                        f"{category} category average of SGD {avgAmount:.2f}"
                    ),
                    "severity": "medium",
                })
                riskScore += ANOMALY_RISK
    except Exception as e:
        logger.warning("Anomaly check failed (non-fatal): %s", e)

    # Clamp risk score to [0.0, 1.0]
    riskScore = max(0.0, min(1.0, riskScore))

    findings = {
        "riskScore": riskScore,
        "duplicates": duplicates,
        "anomalies": anomalies,
    }

    # Summary message
    if riskScore == 0.0:
        summary = f"Fraud check PASSED for {merchant} — no duplicates or anomalies."
    else:
        issues = []
        if duplicates:
            issues.append(f"{len(duplicates)} duplicate(s) found")
        if anomalies:
            issues.append("anomalous amount flagged")
        summary = f"Fraud check flagged issues (risk={riskScore:.2f}): {', '.join(issues)}."

    return {
        "fraudFindings": findings,
        "messages": [AIMessage(content=summary)],
    }
