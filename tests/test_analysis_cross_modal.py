"""Cross-modal analysis tests (Spec B §6.2)."""

from unittest.mock import AsyncMock, patch

import pytest

from agentic_claims.eval_worker.analyses.crossModal import compareCrossModal


@pytest.mark.asyncio
async def testAgreeOnSameVerdict() -> None:
    benchmark = {
        "benchmarkId": "ER-007", "file": "eval/invoices/7.png",
        "scenario": "meals", "question": "?", "groundTruthFacts": [],
        "textOnlyDescription": "ABC Cafe meal, SGD 45",
    }
    imgOut = {"verdict": "pass", "extractedFields": {}, "violations": [], "reasoning": "",
              "latencyMs": 10, "llmCalls": 4, "costUsd": 0.02}
    textOut = {"verdict": "pass", "extractedFields": {}, "violations": [], "reasoning": "",
               "latencyMs": 10, "llmCalls": 4, "costUsd": 0.02}

    with patch("agentic_claims.eval_worker.analyses.crossModal.AgenticPipeline") as mockP:
        mockP.side_effect = lambda textOnly=False: type("X", (), {
            "runBenchmark": AsyncMock(return_value=textOut if textOnly else imgOut)
        })()
        result = await compareCrossModal(benchmark)

    assert result["agree"] is True
    assert result["verdictImageText"] == "pass"
    assert result["verdictTextOnly"] == "pass"


@pytest.mark.asyncio
async def testDisagreeFlagged() -> None:
    benchmark = {
        "benchmarkId": "ER-019", "file": "eval/invoices/19.pdf",
        "scenario": "blurry receipt", "question": "?", "groundTruthFacts": [],
        "textOnlyDescription": "receipt quality too low",
    }
    imgOut = {"verdict": "requiresReview", "extractedFields": {}, "violations": [], "reasoning": "",
              "latencyMs": 10, "llmCalls": 4, "costUsd": 0.02}
    textOut = {"verdict": "pass", "extractedFields": {}, "violations": [], "reasoning": "",
               "latencyMs": 10, "llmCalls": 4, "costUsd": 0.02}
    with patch("agentic_claims.eval_worker.analyses.crossModal.AgenticPipeline") as mockP:
        mockP.side_effect = lambda textOnly=False: type("X", (), {
            "runBenchmark": AsyncMock(return_value=textOut if textOnly else imgOut)
        })()
        result = await compareCrossModal(benchmark)
    assert result["agree"] is False


@pytest.mark.asyncio
async def testSkippedWhenNoFile() -> None:
    """RAGAS items have no image — cross-modal returns None verdicts."""
    benchmark = {"benchmarkId": "RAGAS-001", "file": "", "scenario": "policy Q"}
    result = await compareCrossModal(benchmark)
    assert result["agree"] is None
    assert result["verdictImageText"] is None
    assert result["verdictTextOnly"] is None
