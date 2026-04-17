"""Shared contract for Spec B pipelines (agentic, baseline_prompt, baseline_rules)."""

from __future__ import annotations

from typing import Protocol, TypedDict


class PipelineOutput(TypedDict):
    verdict: str
    extractedFields: dict
    violations: list[dict]
    reasoning: str
    latencyMs: int
    llmCalls: int
    costUsd: float


class Pipeline(Protocol):
    name: str

    async def runBenchmark(self, benchmark: dict) -> PipelineOutput: ...
