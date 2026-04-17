"""Verifier judge analysis tests (Spec B §6.3)."""

import pytest

from agentic_claims.eval_worker.analyses.verifierJudge import computeVerifierAgree


def testAgreeWhenScoresWithinThreshold() -> None:
    result = computeVerifierAgree(primaryScore=0.8, verifierScore=0.9, threshold=0.25)
    assert result["verifierAgree"] is True
    assert result["delta"] == pytest.approx(0.1)


def testDisagreeWhenDeltaAboveThreshold() -> None:
    result = computeVerifierAgree(primaryScore=0.8, verifierScore=0.4, threshold=0.25)
    assert result["verifierAgree"] is False
    assert result["delta"] == pytest.approx(0.4)


def testExactThresholdIsAgree() -> None:
    result = computeVerifierAgree(primaryScore=0.5, verifierScore=0.75, threshold=0.25)
    assert result["verifierAgree"] is True
