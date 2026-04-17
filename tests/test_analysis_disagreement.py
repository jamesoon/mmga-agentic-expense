"""Aggregate disagreement analysis tests (Spec B §6.4)."""

import pytest

from agentic_claims.eval_worker.analyses.disagreement import computeDisagreementScore


def testPerfectAgreementYieldsZero() -> None:
    score = computeDisagreementScore(
        consistencyScore=1.0,
        crossModalAgree=True,
        primaryScore=0.9,
        verifierScore=0.9,
        threshold=0.25,
    )
    assert score == 0.0


def testAllMaxDisagreementYieldsOne() -> None:
    score = computeDisagreementScore(
        consistencyScore=0.0,
        crossModalAgree=False,
        primaryScore=0.0,
        verifierScore=1.0,
        threshold=0.25,
    )
    assert 0.95 <= score <= 1.0


def testWeightedCompositeMid() -> None:
    score = computeDisagreementScore(
        consistencyScore=0.5,
        crossModalAgree=True,
        primaryScore=0.5,
        verifierScore=0.5,
        threshold=0.25,
    )
    assert score == pytest.approx(0.20, abs=0.01)


def testCrossModalNoneTreatedAsZeroContribution() -> None:
    """RAGAS items (no image) → crossModalAgree=None; should not penalise."""
    score = computeDisagreementScore(
        consistencyScore=1.0,
        crossModalAgree=None,
        primaryScore=0.9,
        verifierScore=0.9,
        threshold=0.25,
    )
    assert score == 0.0
