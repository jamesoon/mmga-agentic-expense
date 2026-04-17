"""Verifier judge disagreement analysis (Spec B §6.3). Pure function."""

from __future__ import annotations


def computeVerifierAgree(
    *,
    primaryScore: float,
    verifierScore: float,
    threshold: float = 0.25,
) -> dict:
    delta = abs(primaryScore - verifierScore)
    return {
        "primaryScore": float(primaryScore),
        "verifierScore": float(verifierScore),
        "delta": delta,
        "verifierAgree": delta <= threshold,
    }
