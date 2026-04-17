"""Hard monetary ceilings (Spec A B5) — deterministic, no LLM."""

from __future__ import annotations

from typing import Any


def evaluateHardCaps(
    *,
    receiptTotalSgd: float,
    claimTotalSgd: float,
    monthlyTotalSgd: float,
    settings: Any,
) -> dict[str, Any]:
    """Return {"tripped": bool, "reasons": list[str]}.

    Deterministic — compares three running totals against the three
    configured ceilings. Tripping any ceiling triggers auto-escalation
    in the compliance node (see Phase 8).
    """
    reasons: list[str] = []
    if receiptTotalSgd > settings.hard_cap_per_receipt_sgd:
        reasons.append(
            f"per-receipt cap ({settings.hard_cap_per_receipt_sgd} SGD) "
            f"exceeded: {receiptTotalSgd}"
        )
    if claimTotalSgd > settings.hard_cap_per_claim_sgd:
        reasons.append(
            f"per-claim cap ({settings.hard_cap_per_claim_sgd} SGD) "
            f"exceeded: {claimTotalSgd}"
        )
    if monthlyTotalSgd > settings.hard_cap_per_employee_per_month_sgd:
        reasons.append(
            f"per-employee-per-month cap "
            f"({settings.hard_cap_per_employee_per_month_sgd} SGD) "
            f"exceeded: {monthlyTotalSgd}"
        )
    return {"tripped": bool(reasons), "reasons": reasons}
