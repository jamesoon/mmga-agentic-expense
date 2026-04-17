"""Cost tracker + circuit-breaker tests."""

import pytest

from agentic_claims.eval_worker.cost import CostCapExceeded, CostTracker


def testInitialCostIsZero() -> None:
    t = CostTracker(capUsd=5.0)
    assert t.totalUsd == 0.0


def testAccumulatesCost() -> None:
    t = CostTracker(capUsd=5.0)
    t.record(2.0)
    t.record(1.5)
    assert t.totalUsd == 3.5


def testRaisesOnCapExceeded() -> None:
    t = CostTracker(capUsd=1.0)
    t.record(0.5)
    with pytest.raises(CostCapExceeded):
        t.record(0.6)


def testExactCapDoesNotRaise() -> None:
    t = CostTracker(capUsd=1.0)
    t.record(1.0)
    assert t.totalUsd == 1.0


def testNegativeCostRejected() -> None:
    t = CostTracker(capUsd=1.0)
    with pytest.raises(ValueError):
        t.record(-0.1)
