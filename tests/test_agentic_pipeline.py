"""Agentic pipeline (in-process LangGraph wrapper) tests."""

from unittest.mock import AsyncMock, patch

import pytest

from agentic_claims.eval_worker.baselines.agentic import AgenticPipeline


def testNameIsAgentic() -> None:
    assert AgenticPipeline().name == "agentic"


@pytest.mark.asyncio
async def testRunBenchmarkInvokesGraph() -> None:
    fakeState = {
        "messages": [],
        "extractedReceipt": {"fields": {"category": "meals", "merchant": "ABC", "totalAmountSgd": 40}},
        "complianceFindings": {"verdict": "pass", "finalVerdict": "pass", "summary": "ok"},
        "violations": [],
    }
    with patch("agentic_claims.eval_worker.baselines.agentic.buildGraph") as mockBuild:
        fakeCompiled = type("G", (), {})()
        fakeCompiled.ainvoke = AsyncMock(return_value=fakeState)
        mockBuild.return_value.compile.return_value = fakeCompiled

        benchmark = {
            "benchmarkId": "ER-007",
            "file": "eval/invoices/7.png",
            "scenario": "meals claim",
            "groundTruthFacts": [],
        }
        out = await AgenticPipeline().runBenchmark(benchmark)

    assert out["verdict"] == "pass"
    assert out["llmCalls"] >= 0
