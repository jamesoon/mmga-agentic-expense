"""Justification coherence gate (Spec A B2).

Pure function — no I/O. Returns (ok, human-readable reason).
"""

from __future__ import annotations

import re

_STOPWORDS = {
    "the","and","of","to","a","in","is","it","for","on","at","by",
    "with","an","be","or","this","that","i","you","we","they","he","she",
    "was","were","are","am","been","being","do","does","did","have","has","had",
    "will","would","could","should","can","may","might","must","shall",
    "my","your","our","their","his","her","its",
}

_CATEGORY_KEYWORDS = {
    "meals", "meal", "lunch", "dinner", "breakfast", "food", "restaurant",
    "transport", "travel", "taxi", "grab", "train", "bus", "flight", "airport",
    "accommodation", "hotel", "lodging", "stay", "overnight",
    "office", "supplies", "stationery", "printer", "paper",
    "client", "clients", "customer", "customers", "vendor", "supplier",
    "training", "course", "workshop", "seminar", "conference",
    "emergency", "medical", "hospital", "clinic",
    "team", "department",
}

_RECOGNISED_REASONS = [
    re.compile(r"client\s+(meet|lunch|dinner|meal|call|visit)", re.IGNORECASE),
    re.compile(r"(business|work|company)\s+travel", re.IGNORECASE),
    re.compile(r"after[-\s]hours|overtime", re.IGNORECASE),
    re.compile(r"team\s+(lunch|dinner|offsite|building)", re.IGNORECASE),
]

_MIN_LENGTH = 10
_MIN_NON_STOPWORD_RATIO = 0.3


def checkJustificationCoherence(text: str) -> tuple[bool, str]:
    """Return (ok, reason). ok=True means justification is substantive."""
    if text is None or not text.strip():
        return False, "Justification is empty."

    normalized = text.strip().lower()
    if len(normalized) < _MIN_LENGTH:
        return False, f"Justification is too short (<{_MIN_LENGTH} chars)."

    tokens = re.findall(r"[a-z]+", normalized)
    if not tokens:
        return False, "Justification contains no recognisable words."

    nonStopCount = sum(1 for t in tokens if t not in _STOPWORDS)
    ratio = nonStopCount / len(tokens)
    if ratio < _MIN_NON_STOPWORD_RATIO:
        return False, "Justification is mostly stopwords — provide a concrete reason."

    hasCategory = any(t in _CATEGORY_KEYWORDS for t in tokens)
    hasRecognised = any(p.search(normalized) for p in _RECOGNISED_REASONS)
    if not (hasCategory or hasRecognised):
        return False, "Justification does not reference a known expense category or reason."

    return True, "Justification looks substantive."
