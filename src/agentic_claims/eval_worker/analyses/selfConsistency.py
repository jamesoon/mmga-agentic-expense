"""Self-consistency analysis (Spec B §6.1).

consistencyScore = 1 - (H_observed / log2(N)) where H_observed is the
Shannon entropy of observed verdicts.
"""

from __future__ import annotations

import math
from collections import Counter


def computeConsistencyScore(verdicts: list[str]) -> float:
    if not verdicts:
        return 0.0
    n = len(verdicts)
    if n == 1:
        return 1.0
    counts = Counter(verdicts)
    observedEntropy = 0.0
    for c in counts.values():
        p = c / n
        if p > 0:
            observedEntropy -= p * math.log2(p)
    maxEntropy = math.log2(n)
    if maxEntropy == 0:
        return 1.0
    return max(0.0, 1.0 - (observedEntropy / maxEntropy))
