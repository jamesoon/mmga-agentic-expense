"""Self-consistency analysis tests (Spec B §6.1)."""

import math

from agentic_claims.eval_worker.analyses.selfConsistency import computeConsistencyScore


def testAllSameVerdictsScoreOne() -> None:
    assert computeConsistencyScore(["pass", "pass", "pass"]) == 1.0


def testTwoDifferentVerdictsScoresMid() -> None:
    s = computeConsistencyScore(["pass", "pass", "fail"])
    assert 0.3 < s < 0.9


def testAllDifferentVerdictsScoreZero() -> None:
    s = computeConsistencyScore(["pass", "fail", "requiresReview"])
    assert math.isclose(s, 0.0, abs_tol=0.01)


def testEmptyVerdictsReturnsZero() -> None:
    assert computeConsistencyScore([]) == 0.0


def testSingleVerdictReturnsOne() -> None:
    assert computeConsistencyScore(["pass"]) == 1.0
