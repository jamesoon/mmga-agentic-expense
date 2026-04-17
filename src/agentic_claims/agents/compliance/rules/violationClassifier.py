"""Deterministic violation classification rule table (Spec A §5)."""

from __future__ import annotations


_HARD_TYPES = {
    "alcohol_outside_allowlist",
    "non_claimable_personal",
    "non_claimable_category",
    "duplicate_receipt",
}

_SOFT_TYPES = {
    "missing_preferred_vendor",
    "outside_working_hours",
}

_DEFAULT = "soft"


def classifyViolation(v: dict) -> str:
    """Return one of: 'soft', 'soft-plus', 'hard'."""
    vType = (v or {}).get("type", "")
    if vType in _HARD_TYPES:
        return "hard"
    if vType == "amount_over_cap":
        amount = float(v.get("amount", 0) or 0)
        cap = float(v.get("cap", 0) or 0)
        hardCap = v.get("hardCap")
        if hardCap is not None and amount > float(hardCap):
            return "hard"
        if cap > 0 and amount / cap >= 1.5:
            return "soft-plus"
        return "soft"
    if vType in _SOFT_TYPES:
        return "soft"
    return _DEFAULT
