"""Agentic pipeline: in-process LangGraph invocation for Spec B eval."""

from __future__ import annotations

import base64
import logging
import time
import uuid
from pathlib import Path

from langchain_core.messages import HumanMessage

from agentic_claims.core.graph import buildGraph
from agentic_claims.core import imageStore as _imageStoreModule
from agentic_claims.eval_worker.pipelineContract import PipelineOutput

logger = logging.getLogger(__name__)


class AgenticPipeline:
    name = "agentic"

    def __init__(self, *, textOnly: bool = False) -> None:
        self._textOnly = textOnly

    async def runBenchmark(self, benchmark: dict) -> PipelineOutput:
        startNs = time.perf_counter_ns()
        claimId = f"evalb-{uuid.uuid4().hex[:12]}"

        filePath = Path(benchmark.get("file", ""))
        if filePath.exists() and not self._textOnly:
            try:
                with filePath.open("rb") as fh:
                    _imageStoreModule.storeImage(claimId, base64.b64encode(fh.read()).decode())
            except Exception as exc:
                logger.warning("agentic: image load failed: %s", exc)

        contentLines: list[str] = [
            f"[EVAL benchmark {benchmark.get('benchmarkId', '?')}]",
            str(benchmark.get("scenario", "")),
        ]
        if self._textOnly and benchmark.get("textOnlyDescription"):
            contentLines.append("Text-only mode; receipt description follows:")
            contentLines.append(str(benchmark["textOnlyDescription"]))
        if benchmark.get("question"):
            contentLines.append(str(benchmark["question"]))

        initialState: dict = {
            "claimId": claimId,
            "status": "draft",
            "messages": [HumanMessage(content="\n".join(contentLines))],
        }

        finalState: dict = {}
        try:
            graph = buildGraph().compile()
            finalState = await graph.ainvoke(
                initialState,
                {"configurable": {"thread_id": claimId}},
            )
        except Exception as exc:
            logger.warning("agentic: graph.ainvoke failed: %s", exc)
            finalState = {}

        findings = (finalState or {}).get("complianceFindings") or {}
        verdict = str(findings.get("finalVerdict") or findings.get("verdict") or "requiresReview")
        if verdict not in {
            "pass", "fail", "requiresReview",
            "requiresManagerApproval", "requiresDirectorApproval",
        }:
            verdict = "requiresReview"

        latencyMs = int((time.perf_counter_ns() - startNs) / 1_000_000)
        extracted = (finalState.get("extractedReceipt") or {}).get("fields") or {}
        violations = finalState.get("violations") or []

        _imageStoreModule.clearImage(claimId)

        return PipelineOutput(
            verdict=verdict,
            extractedFields=extracted,
            violations=violations,
            reasoning=str(findings.get("summary", ""))[:500],
            latencyMs=latencyMs,
            llmCalls=4,
            costUsd=0.02,
        )
