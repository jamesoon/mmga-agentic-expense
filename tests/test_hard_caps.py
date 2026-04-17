"""Hard monetary ceiling tests (B5)."""

from agentic_claims.agents.compliance.rules.hardCaps import evaluateHardCaps


class _FakeSettings:
    hard_cap_per_receipt_sgd = 5000.0
    hard_cap_per_claim_sgd = 10000.0
    hard_cap_per_employee_per_month_sgd = 20000.0


def testNoCapTripped() -> None:
    result = evaluateHardCaps(
        receiptTotalSgd=100,
        claimTotalSgd=500,
        monthlyTotalSgd=3000,
        settings=_FakeSettings(),
    )
    assert result["tripped"] is False


def testReceiptCapTripped() -> None:
    result = evaluateHardCaps(
        receiptTotalSgd=5001,
        claimTotalSgd=5001,
        monthlyTotalSgd=5001,
        settings=_FakeSettings(),
    )
    assert result["tripped"] is True
    assert "per-receipt" in "\n".join(result["reasons"])


def testClaimCapTripped() -> None:
    result = evaluateHardCaps(
        receiptTotalSgd=4000,
        claimTotalSgd=10001,
        monthlyTotalSgd=10001,
        settings=_FakeSettings(),
    )
    assert result["tripped"] is True
    assert "per-claim" in "\n".join(result["reasons"])


def testMonthlyCapTripped() -> None:
    result = evaluateHardCaps(
        receiptTotalSgd=100,
        claimTotalSgd=500,
        monthlyTotalSgd=20001,
        settings=_FakeSettings(),
    )
    assert result["tripped"] is True
    assert "per-employee-per-month" in "\n".join(result["reasons"])
