"""Aggregate disagreement analysis (Spec B §6.4).

disagreementScore = 0.4 * (1 - consistencyScore)
                  + 0.3 * (1 - crossModalAgree_numeric)
                  + 0.3 * normalised_verifier_delta
"""

from __future__ import annotations

from typing import Optional


def computeDisagreementScore(
    *,
    consistencyScore: float,
    crossModalAgree: Optional[bool],
    primaryScore: float,
    verifierScore: float,
    threshold: float = 0.25,
) -> float:
    consistencyComponent = (1.0 - max(0.0, min(1.0, consistencyScore))) * 0.4

    if crossModalAgree is None:
        crossComponent = 0.0
    else:
        crossComponent = (0.0 if crossModalAgree else 1.0) * 0.3

    delta = abs(primaryScore - verifierScore)
    verifierComponent = min(1.0, delta / max(threshold, 0.01)) * 0.3

    total = consistencyComponent + crossComponent + verifierComponent
    return max(0.0, min(1.0, total))
