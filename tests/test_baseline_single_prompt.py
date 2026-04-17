"""Baseline 1 — single-prompt pipeline tests."""

from unittest.mock import AsyncMock, patch

import pytest

from agentic_claims.eval_worker.baselines.singlePrompt import SinglePromptPipeline


@pytest.mark.asyncio
async def testNameIsBaselinePrompt() -> None:
    pipeline = SinglePromptPipeline()
    assert pipeline.name == "baseline_prompt"


@pytest.mark.asyncio
async def testReturnsPipelineOutputShape() -> None:
    fakeLlmResp = type("R", (), {
        "content": '{"category":"meals","extractedFields":{"merchant":"ABC","totalAmountSgd":45},'
                   '"violations":[],"verdict":"pass","reasoning":"ok"}',
    })()
    benchmark = {
        "benchmarkId": "ER-007",
        "file": "eval/invoices/7.png",
        "scenario": "meals claim",
        "question": "what verdict?",
        "groundTruthFacts": [],
    }
    with patch("agentic_claims.eval_worker.baselines.singlePrompt.buildAgentLlm") as mockLlm, \
         patch("agentic_claims.eval_worker.baselines.singlePrompt.OpenRouterClient") as mockOr:
        mockLlm.return_value.ainvoke = AsyncMock(return_value=fakeLlmResp)
        mockOr.return_value.callVlm = AsyncMock(return_value="merchant: ABC, total: 45")

        pipeline = SinglePromptPipeline()
        out = await pipeline.runBenchmark(benchmark)

    assert out["verdict"] == "pass"
    assert out["costUsd"] >= 0.0
    assert isinstance(out["latencyMs"], int)


@pytest.mark.asyncio
async def testMalformedLlmResponseReturnsRequiresReview() -> None:
    fakeLlmResp = type("R", (), {"content": "not json"})()
    benchmark = {"benchmarkId": "ER-007", "file": "x", "scenario": "s", "question": "q", "groundTruthFacts": []}
    with patch("agentic_claims.eval_worker.baselines.singlePrompt.buildAgentLlm") as mockLlm, \
         patch("agentic_claims.eval_worker.baselines.singlePrompt.OpenRouterClient") as mockOr:
        mockLlm.return_value.ainvoke = AsyncMock(return_value=fakeLlmResp)
        mockOr.return_value.callVlm = AsyncMock(return_value="")

        pipeline = SinglePromptPipeline()
        out = await pipeline.runBenchmark(benchmark)
    assert out["verdict"] == "requiresReview"
