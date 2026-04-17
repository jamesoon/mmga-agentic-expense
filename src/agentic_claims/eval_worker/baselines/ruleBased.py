"""Baseline 2: rule-based deterministic pipeline (Spec B §5.2). Zero LLM calls."""

from __future__ import annotations

import logging
import re
import time
from pathlib import Path

from agentic_claims.core.config import getSettings
from agentic_claims.eval_worker.pipelineContract import PipelineOutput

logger = logging.getLogger(__name__)

_CATEGORY_KEYWORDS: dict[str, set[str]] = {
    "meals": {
        "starbucks", "cafe", "coffee", "restaurant", "bistro", "mcdonald",
        "burger", "pizza", "dinner", "lunch", "breakfast",
    },
    "accommodation": {"marriott", "hyatt", "hotel", "hilton", "four seasons", "lodging"},
    "transport": {"grab", "taxi", "uber", "mrt", "bus", "flight", "airline", "sia", "singapore airlines"},
    "office_supplies": {"staples", "office depot", "printer", "stationery", "paper"},
}

_DATE_RE = re.compile(r"(\d{4}-\d{2}-\d{2})")
_TOTAL_RE = re.compile(r"(?<!\w)(?:total|amount)[^\d]*(\d+(?:[.,]\d{2}))", re.IGNORECASE)
_CURRENCY_RE = re.compile(r"\b(SGD|USD|VND|EUR|GBP|MYR|THB|JPY)\b", re.IGNORECASE)


def _ocrImage(path: str) -> str:
    try:
        import pytesseract
        from PIL import Image  # type: ignore
    except ImportError:
        logger.warning("Tesseract/Pillow not available — rule-based pipeline returns empty OCR")
        return ""
    filePath = Path(path)
    if not filePath.exists():
        return ""
    try:
        img = Image.open(filePath)
        return pytesseract.image_to_string(img)
    except Exception as exc:
        logger.warning("OCR failed for %s: %s", path, exc)
        return ""


def classifyCategory(merchant: str, lineItems: list[str]) -> str:
    haystack = " ".join([(merchant or ""), *lineItems]).lower()
    for category, keywords in _CATEGORY_KEYWORDS.items():
        if any(kw in haystack for kw in keywords):
            return category
    return "general"


def extractFields(ocrText: str) -> dict:
    lines = [ln.strip() for ln in (ocrText or "").splitlines() if ln.strip()]
    merchant = lines[0] if lines else "unknown"

    dateMatch = _DATE_RE.search(ocrText or "")
    totalMatch = _TOTAL_RE.search(ocrText or "")
    currencyMatch = _CURRENCY_RE.search(ocrText or "")

    currency = currencyMatch.group(1).upper() if currencyMatch else "SGD"
    totalRaw = totalMatch.group(1) if totalMatch else "0"
    total = float(totalRaw.replace(",", "."))
    date = dateMatch.group(1) if dateMatch else ""

    return {
        "merchant": merchant,
        "date": date,
        "currency": currency,
        "totalAmountSgd": total if currency == "SGD" else 0.0,
        "totalAmountOriginal": total,
    }


class RuleBasedPipeline:
    name = "baseline_rules"

    def __init__(self) -> None:
        try:
            self._settings = getSettings()
        except Exception:
            self._settings = None

    async def runBenchmark(self, benchmark: dict) -> PipelineOutput:
        startNs = time.perf_counter_ns()
        ocrText = _ocrImage(str(benchmark.get("file", "")))
        fields = extractFields(ocrText)
        category = classifyCategory(fields["merchant"], [])

        violations: list[dict] = []
        amount = float(fields["totalAmountSgd"])
        hardCap = getattr(self._settings, "hard_cap_per_receipt_sgd", 5000.0) if self._settings else 5000.0
        if amount > hardCap:
            violations.append({"type": "amount_over_cap", "amount": amount, "cap": hardCap})

        if violations:
            verdict = "requiresDirectorApproval"
        elif amount == 0 or not fields["date"]:
            verdict = "requiresReview"
        else:
            verdict = "pass"

        reasoning = (
            f"Rule-based pipeline: category={category}, "
            f"amount={amount} {fields['currency']}, violations={len(violations)}."
        )
        latencyMs = int((time.perf_counter_ns() - startNs) / 1_000_000)

        return PipelineOutput(
            verdict=verdict,
            extractedFields={**fields, "category": category},
            violations=violations,
            reasoning=reasoning,
            latencyMs=latencyMs,
            llmCalls=0,
            costUsd=0.0,
        )
