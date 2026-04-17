"""Top-level eval run orchestration (Spec B §8.3)."""

from __future__ import annotations

import logging

from agentic_claims.eval_worker.baselines.agentic import AgenticPipeline
from agentic_claims.eval_worker.baselines.ruleBased import RuleBasedPipeline
from agentic_claims.eval_worker.baselines.singlePrompt import SinglePromptPipeline
from agentic_claims.eval_worker.pipelineContract import PipelineOutput

logger = logging.getLogger(__name__)


async def runBenchmarkAcrossPipelines(
    benchmark: dict, *, iterations: int = 3
) -> dict[str, list[PipelineOutput]]:
    """Run one benchmark N times per pipeline and return per-pipeline output lists."""
    pipelines = {
        "agentic": AgenticPipeline(),
        "baseline_prompt": SinglePromptPipeline(),
        "baseline_rules": RuleBasedPipeline(),
    }
    out: dict[str, list[PipelineOutput]] = {name: [] for name in pipelines}
    for name, pipeline in pipelines.items():
        for _ in range(iterations):
            try:
                result = await pipeline.runBenchmark(benchmark)
            except Exception as exc:
                logger.warning(
                    "pipeline %s benchmark %s failed: %s",
                    name, benchmark.get("benchmarkId"), exc,
                )
                result = PipelineOutput(
                    verdict="requiresReview",
                    extractedFields={},
                    violations=[],
                    reasoning=f"error: {exc}"[:200],
                    latencyMs=0,
                    llmCalls=0,
                    costUsd=0.0,
                )
            out[name].append(result)
    return out


import json
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from sqlalchemy import text

from agentic_claims.core.config import getSettings
from agentic_claims.eval_worker.analyses.crossModal import compareCrossModal
from agentic_claims.eval_worker.analyses.disagreement import computeDisagreementScore
from agentic_claims.eval_worker.analyses.selfConsistency import computeConsistencyScore
from agentic_claims.eval_worker.analyses.verifierJudge import computeVerifierAgree
from agentic_claims.eval_worker.cost import CostCapExceeded, CostTracker
from agentic_claims.web.db import getAsyncSession

_RESULTS_DIR = Path(__file__).resolve().parents[3] / "eval" / "results"


def _loadBenchmarks() -> list[dict]:
    """Import the current benchmark dataset — MMGA for now, SROIE+RAGAS in a later phase."""
    try:
        from eval.src.dataset import BENCHMARKS  # noqa: WPS433 (local import — avoid loading heavy eval deps at module load)
        return list(BENCHMARKS)
    except Exception as exc:
        logger.warning("failed to load eval/src/dataset.BENCHMARKS: %s", exc)
        return []


async def _updateRunStatus(runId: int, status: str, *, summary: dict[str, Any] | None = None) -> None:
    async with getAsyncSession() as session:
        params: dict[str, Any] = {"id": runId, "status": status}
        if summary is not None:
            params["summary"] = json.dumps(summary)
            await session.execute(text(
                "UPDATE eval_runs SET status=:status, "
                "summary_json=cast(:summary as jsonb), "
                "finished_at=CASE WHEN :status IN ('finished','failed','interrupted') "
                "                 THEN now() ELSE finished_at END "
                "WHERE id=:id"
            ), params)
        else:
            await session.execute(text("UPDATE eval_runs SET status=:status WHERE id=:id"), params)
        await session.commit()


async def _insertJudgment(runId: int, judgment: dict) -> None:
    async with getAsyncSession() as session:
        await session.execute(text("""
            INSERT INTO eval_judgments
              (run_id, benchmark_id, pipeline, self_consistency_runs,
               consistency_score, cross_modal_verdict, cross_modal_agree,
               primary_judge_score, verifier_judge_score, verifier_agree,
               disagreement_score, cost_usd, reasoning_digest)
            VALUES
              (:run_id, :bm, :pipeline, cast(:scr as jsonb),
               :cs, :cmv, :cma,
               :pj, :vj, :va,
               :ds, :cost, :reason)
        """), {
            "run_id": runId,
            "bm": judgment["benchmarkId"],
            "pipeline": judgment["pipeline"],
            "scr": json.dumps(judgment["selfConsistencyRuns"]),
            "cs": judgment["consistencyScore"],
            "cmv": judgment.get("crossModalVerdict"),
            "cma": judgment.get("crossModalAgree"),
            "pj": judgment["primaryJudgeScore"],
            "vj": judgment["verifierJudgeScore"],
            "va": judgment["verifierAgree"],
            "ds": judgment["disagreementScore"],
            "cost": judgment["costUsd"],
            "reason": (judgment.get("reasoningDigest") or "")[:500],
        })
        await session.commit()


async def executeRun(runId: int) -> None:
    """Top-level run — three pipelines × benchmarks × N iterations + analyses."""
    settings = getSettings()
    tracker = CostTracker(capUsd=settings.eval_max_cost_usd_per_run)
    iso = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H-%M-%S")
    _RESULTS_DIR.mkdir(parents=True, exist_ok=True)
    resultsPath = _RESULTS_DIR / f"{iso}.json"

    await _updateRunStatus(runId, "running")
    aggregate: list[dict] = []

    try:
        benchmarks = _loadBenchmarks()
        for bm in benchmarks:
            acrossPipelines = await runBenchmarkAcrossPipelines(
                bm, iterations=settings.eval_self_consistency_runs
            )
            crossModal = await compareCrossModal(bm)
            for pipeName, outputs in acrossPipelines.items():
                verdicts = [o["verdict"] for o in outputs]
                consistency = computeConsistencyScore(verdicts)
                perBenchmarkCost = sum(o["costUsd"] for o in outputs)
                try:
                    tracker.record(perBenchmarkCost)
                except CostCapExceeded as exc:
                    await _updateRunStatus(runId, "failed", summary={
                        "error": str(exc), "costUsd": tracker.totalUsd,
                    })
                    return

                expectedDecision = bm.get("expectedDecision", "")
                primaryScore = 1.0 if verdicts and verdicts[0] == expectedDecision else 0.4
                verifierScore = primaryScore  # TODO: replace with a real verifier-model call in a later phase.
                verifierAgreeDict = computeVerifierAgree(
                    primaryScore=primaryScore, verifierScore=verifierScore,
                    threshold=settings.eval_disagreement_threshold,
                )
                crossAgreeForRow = crossModal["agree"] if pipeName == "agentic" else None
                crossVerdictForRow = crossModal["verdictTextOnly"] if pipeName == "agentic" else None
                disagreementScore = computeDisagreementScore(
                    consistencyScore=consistency,
                    crossModalAgree=crossAgreeForRow,
                    primaryScore=primaryScore,
                    verifierScore=verifierScore,
                    threshold=settings.eval_disagreement_threshold,
                )
                judgment = {
                    "benchmarkId": bm["benchmarkId"],
                    "pipeline": pipeName,
                    "selfConsistencyRuns": [
                        {"verdict": o["verdict"], "score": primaryScore, "latencyMs": o["latencyMs"]}
                        for o in outputs
                    ],
                    "consistencyScore": consistency,
                    "crossModalVerdict": crossVerdictForRow,
                    "crossModalAgree": crossAgreeForRow,
                    "primaryJudgeScore": primaryScore,
                    "verifierJudgeScore": verifierScore,
                    "verifierAgree": verifierAgreeDict["verifierAgree"],
                    "disagreementScore": disagreementScore,
                    "costUsd": perBenchmarkCost,
                    "reasoningDigest": (outputs[0].get("reasoning", "") if outputs else "")[:500],
                }
                await _insertJudgment(runId, judgment)
                aggregate.append(judgment)

        resultsPath.write_text(json.dumps({"runId": runId, "judgments": aggregate}, default=str))

        agenticRows = [j for j in aggregate if j["pipeline"] == "agentic"]
        b1Rows = [j for j in aggregate if j["pipeline"] == "baseline_prompt"]
        b2Rows = [j for j in aggregate if j["pipeline"] == "baseline_rules"]

        def pct(rows):
            return sum(r["primaryJudgeScore"] for r in rows) / len(rows) if rows else 0.0

        summary = {
            "resultsPath": str(resultsPath),
            "agenticPct": pct(agenticRows),
            "b1Pct": pct(b1Rows),
            "b2Pct": pct(b2Rows),
            "totalCostUsd": tracker.totalUsd,
        }
        await _updateRunStatus(runId, "finished", summary=summary)
    except Exception as exc:
        logger.exception("executeRun failure for run %s", runId)
        await _updateRunStatus(runId, "failed", summary={"error": str(exc)})
        raise
