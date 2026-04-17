"""Cumulative cost tracker for Spec B eval runs with a hard circuit-breaker."""

from __future__ import annotations


class CostCapExceeded(Exception):
    """Raised when cumulative cost exceeds the configured per-run cap."""


class CostTracker:
    def __init__(self, capUsd: float) -> None:
        self._capUsd = float(capUsd)
        self._totalUsd = 0.0

    @property
    def totalUsd(self) -> float:
        return self._totalUsd

    @property
    def capUsd(self) -> float:
        return self._capUsd

    def record(self, delta: float) -> None:
        if delta < 0:
            raise ValueError(f"Cost delta must be non-negative, got {delta}")
        projected = self._totalUsd + float(delta)
        if projected > self._capUsd:
            raise CostCapExceeded(
                f"Run cost {projected:.4f} USD would exceed cap {self._capUsd:.4f} USD"
            )
        self._totalUsd = projected
