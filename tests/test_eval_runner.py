"""Eval runner — one benchmark through all three mocked pipelines."""

from unittest.mock import AsyncMock, patch

import pytest

from agentic_claims.eval_worker.runner import runBenchmarkAcrossPipelines


@pytest.mark.asyncio
async def testRunBenchmarkAcrossPipelinesReturnsThreeOutputs() -> None:
    benchmark = {
        "benchmarkId": "ER-007", "file": "eval/invoices/7.png",
        "scenario": "meals", "question": "?", "groundTruthFacts": [],
    }
    fakeOut = {"verdict": "pass", "extractedFields": {}, "violations": [],
               "reasoning": "", "latencyMs": 1, "llmCalls": 0, "costUsd": 0.0}

    with patch("agentic_claims.eval_worker.runner.AgenticPipeline") as a, \
         patch("agentic_claims.eval_worker.runner.SinglePromptPipeline") as b, \
         patch("agentic_claims.eval_worker.runner.RuleBasedPipeline") as c:
        a.return_value.runBenchmark = AsyncMock(return_value=fakeOut)
        b.return_value.runBenchmark = AsyncMock(return_value=fakeOut)
        c.return_value.runBenchmark = AsyncMock(return_value=fakeOut)

        results = await runBenchmarkAcrossPipelines(benchmark, iterations=2)

    assert set(results) == {"agentic", "baseline_prompt", "baseline_rules"}
    assert all(len(v) == 2 for v in results.values())


@pytest.mark.asyncio
async def testPipelineExceptionProducesErrorOutput() -> None:
    """If a pipeline raises, the runner records an error output and continues."""
    benchmark = {"benchmarkId": "ER-X", "file": "", "scenario": "", "question": "", "groundTruthFacts": []}
    fakeOut = {"verdict": "pass", "extractedFields": {}, "violations": [],
               "reasoning": "", "latencyMs": 1, "llmCalls": 0, "costUsd": 0.0}
    with patch("agentic_claims.eval_worker.runner.AgenticPipeline") as a, \
         patch("agentic_claims.eval_worker.runner.SinglePromptPipeline") as b, \
         patch("agentic_claims.eval_worker.runner.RuleBasedPipeline") as c:
        a.return_value.runBenchmark = AsyncMock(side_effect=RuntimeError("boom"))
        b.return_value.runBenchmark = AsyncMock(return_value=fakeOut)
        c.return_value.runBenchmark = AsyncMock(return_value=fakeOut)

        results = await runBenchmarkAcrossPipelines(benchmark, iterations=1)

    assert results["agentic"][0]["verdict"] == "requiresReview"
    assert "boom" in results["agentic"][0]["reasoning"]
