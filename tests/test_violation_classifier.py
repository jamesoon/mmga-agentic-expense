"""Violation classifier rule-table tests."""

from agentic_claims.agents.compliance.rules.violationClassifier import classifyViolation


def testAmountSoftCapIsSoft() -> None:
    v = {"type": "amount_over_cap", "amount": 120, "cap": 100}
    assert classifyViolation(v) == "soft"


def testAmountJustUnderSoftPlusIsSoft() -> None:
    v = {"type": "amount_over_cap", "amount": 149, "cap": 100}
    assert classifyViolation(v) == "soft"


def testAmountAt150PercentIsSoftPlus() -> None:
    v = {"type": "amount_over_cap", "amount": 150, "cap": 100}
    assert classifyViolation(v) == "soft-plus"


def testAmountAboveHardCapIsHard() -> None:
    v = {"type": "amount_over_cap", "amount": 10000, "cap": 100, "hardCap": 5000}
    assert classifyViolation(v) == "hard"


def testMissingVendorIsSoft() -> None:
    assert classifyViolation({"type": "missing_preferred_vendor"}) == "soft"


def testOutsideHoursIsSoft() -> None:
    assert classifyViolation({"type": "outside_working_hours"}) == "soft"


def testAlcoholIsHard() -> None:
    assert classifyViolation({"type": "alcohol_outside_allowlist"}) == "hard"


def testPersonalIsHard() -> None:
    assert classifyViolation({"type": "non_claimable_personal"}) == "hard"


def testDuplicateReceiptIsHard() -> None:
    assert classifyViolation({"type": "duplicate_receipt"}) == "hard"


def testUnknownTypeDefaultsSoft() -> None:
    assert classifyViolation({"type": "made_up"}) == "soft"
