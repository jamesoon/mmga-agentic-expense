"""Baseline 2 — rule-based pipeline tests (no LLM)."""

from unittest.mock import patch

import pytest

from agentic_claims.eval_worker.baselines.ruleBased import (
    RuleBasedPipeline, classifyCategory, extractFields,
)


def testNameIsBaselineRules() -> None:
    assert RuleBasedPipeline().name == "baseline_rules"


def testCategoryKeywordMeal() -> None:
    assert classifyCategory("starbucks", ["latte", "muffin"]) == "meals"


def testCategoryKeywordHotel() -> None:
    assert classifyCategory("Marriott Singapore", ["room night"]) == "accommodation"


def testCategoryKeywordTaxi() -> None:
    assert classifyCategory("Grab", ["ride"]) == "transport"


def testCategoryKeywordOffice() -> None:
    assert classifyCategory("Staples", ["printer paper"]) == "office_supplies"


def testCategoryUnknownDefaultsGeneral() -> None:
    assert classifyCategory("Zzz Unknown", ["item"]) == "general"


def testExtractFieldsFromOcrText() -> None:
    ocr = "ABC Cafe\n2026-03-15\nSubtotal 40.00\nTotal SGD 45.00\n"
    fields = extractFields(ocr)
    assert fields["merchant"] == "ABC Cafe"
    assert fields["totalAmountSgd"] == pytest.approx(45.00)
    assert fields["currency"] == "SGD"
    assert fields["date"] == "2026-03-15"


def testExtractFieldsDefaultCurrency() -> None:
    ocr = "Some Shop\n2026-01-02\nTotal 12.50\n"
    fields = extractFields(ocr)
    assert fields["currency"] == "SGD"


@pytest.mark.asyncio
async def testRunBenchmarkProducesPipelineOutput() -> None:
    benchmark = {
        "benchmarkId": "ER-007",
        "file": "eval/invoices/7.png",
        "scenario": "meals claim",
        "groundTruthFacts": [],
    }
    with patch(
        "agentic_claims.eval_worker.baselines.ruleBased._ocrImage",
        return_value="ABC Cafe\n2026-03-15\nTotal SGD 45.00\n",
    ):
        out = await RuleBasedPipeline().runBenchmark(benchmark)
    assert out["verdict"] in {
        "pass", "fail", "requiresReview",
        "requiresManagerApproval", "requiresDirectorApproval",
    }
    assert out["llmCalls"] == 0
    assert out["costUsd"] == 0.0
