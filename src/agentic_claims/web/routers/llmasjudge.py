"""Public LLM-as-Judge web router (Spec B).

Author: jamesoon
"""

from __future__ import annotations

import logging
from pathlib import Path

from fastapi import APIRouter, Request
from fastapi.responses import HTMLResponse, JSONResponse
from sqlalchemy import text

from agentic_claims.web.db import getAsyncSession
from agentic_claims.web.templating import templates

logger = logging.getLogger(__name__)
router = APIRouter()

_RESULTS_DIR = Path(__file__).resolve().parents[3] / "eval" / "results"

_VALID_VERDICTS = {
    "pass", "fail", "requiresReview",
    "requiresManagerApproval", "requiresDirectorApproval",
}


@router.get("/llmasjudge", response_class=HTMLResponse)
async def page(request: Request) -> HTMLResponse:
    return templates.TemplateResponse(
        request, "llmasjudge.html", context={"activePage": "llmasjudge"}
    )


@router.get("/llmasjudge/summary")
async def summary() -> JSONResponse:
    try:
        async with getAsyncSession() as session:
            row = await session.execute(text(
                "SELECT id, started_at, status, summary_json "
                "FROM eval_runs WHERE status='finished' "
                "ORDER BY started_at DESC LIMIT 1"
            ))
            rec = row.mappings().first()
    except Exception as exc:
        logger.warning("/llmasjudge/summary DB error: %s", exc)
        return JSONResponse({"error": "database unavailable"}, status_code=503)

    if not rec:
        return JSONResponse({"message": "no finished runs yet"}, status_code=404)
    return JSONResponse({
        "runId": rec["id"],
        "startedAt": rec["started_at"].isoformat() if rec["started_at"] else None,
        "summary": rec["summary_json"] or {},
    })


@router.get("/llmasjudge/runs")
async def runs(page: int = 1) -> JSONResponse:
    pageSize = 10
    offset = max(0, (page - 1) * pageSize)
    try:
        async with getAsyncSession() as session:
            rows = await session.execute(text(
                "SELECT id, started_at, finished_at, status, git_sha, "
                "judge_model, summary_json "
                "FROM eval_runs ORDER BY started_at DESC LIMIT :lim OFFSET :off"
            ), {"lim": pageSize, "off": offset})
            records = [dict(r) for r in rows.mappings().all()]
    except Exception as exc:
        logger.warning("/llmasjudge/runs DB error: %s", exc)
        return JSONResponse({"page": page, "records": []})
    for r in records:
        if r.get("started_at"):
            r["started_at"] = r["started_at"].isoformat()
        if r.get("finished_at"):
            r["finished_at"] = r["finished_at"].isoformat()
    return JSONResponse({"page": page, "records": records})


@router.get("/llmasjudge/runs/{run_id}")
async def runDetail(run_id: int) -> JSONResponse:
    try:
        async with getAsyncSession() as session:
            runRow = (await session.execute(text(
                "SELECT * FROM eval_runs WHERE id=:id"
            ), {"id": run_id})).mappings().first()
            if not runRow:
                return JSONResponse({"error": "not found"}, status_code=404)
            judgments = (await session.execute(text(
                "SELECT * FROM eval_judgments WHERE run_id=:id "
                "ORDER BY benchmark_id, pipeline"
            ), {"id": run_id})).mappings().all()
    except Exception as exc:
        logger.warning("/llmasjudge/runs/%s DB error: %s", run_id, exc)
        return JSONResponse({"error": "database unavailable"}, status_code=503)
    out = {
        "run": {k: (v.isoformat() if hasattr(v, "isoformat") else v) for k, v in dict(runRow).items()},
        "judgments": [dict(j) for j in judgments],
    }
    return JSONResponse(out)


@router.get("/llmasjudge/runs/{run_id}/status")
async def runStatus(run_id: int) -> JSONResponse:
    try:
        async with getAsyncSession() as session:
            r = (await session.execute(text(
                "SELECT status, summary_json FROM eval_runs WHERE id=:id"
            ), {"id": run_id})).mappings().first()
    except Exception as exc:
        logger.warning("/llmasjudge/runs/%s/status DB error: %s", run_id, exc)
        return JSONResponse({"error": "database unavailable"}, status_code=503)
    if not r:
        return JSONResponse({"error": "not found"}, status_code=404)
    progress = (r["summary_json"] or {}).get("progress", {}) if r["summary_json"] else {}
    return JSONResponse({"status": r["status"], "progress": progress})


@router.get("/llmasjudge/analyses/latest")
async def analysesLatest() -> JSONResponse:
    try:
        async with getAsyncSession() as session:
            runRow = (await session.execute(text(
                "SELECT id FROM eval_runs WHERE status='finished' "
                "ORDER BY started_at DESC LIMIT 1"
            ))).mappings().first()
            if not runRow:
                return JSONResponse({"message": "no runs yet"}, status_code=404)
            runId = runRow["id"]
            judgments = (await session.execute(text(
                "SELECT * FROM eval_judgments WHERE run_id=:id"
            ), {"id": runId})).mappings().all()
    except Exception as exc:
        logger.warning("/llmasjudge/analyses/latest DB error: %s", exc)
        return JSONResponse({"error": "database unavailable"}, status_code=503)
    topDisagreement = sorted(judgments, key=lambda j: -float(j["disagreement_score"]))[:5]
    return JSONResponse({
        "runId": runId,
        "judgments": [dict(j) for j in judgments],
        "topDisagreement": [dict(j) for j in topDisagreement],
    })


@router.post("/llmasjudge/run")
async def runStart(request: Request) -> JSONResponse:
    orch = getattr(request.app.state, "evalOrchestrator", None)
    if orch is None:
        return JSONResponse({"error": "eval orchestrator not initialised"}, status_code=503)

    # Local import to avoid circular dependency at module load.
    from agentic_claims.eval_worker.runner import executeRun

    settings = getattr(request.app.state, "settings", None)
    judgeModel = (settings.eval_judge_model if settings else None) or "default"
    verifierModel = settings.eval_verifier_model if settings else "default"

    triggeredBy = (request.client.host if request.client else "anon") + ":public"
    try:
        runId = await orch.enqueue(triggeredBy=triggeredBy, configJson={
            "gitSha": "deployed",
            "judgeModel": judgeModel,
            "verifierModel": verifierModel,
            "resultsPath": "",
        })
    except RuntimeError:
        return JSONResponse({"error": "run already queued or running"}, status_code=409)
    await orch.start(executeRun)
    return JSONResponse({"runId": runId, "status": "queued"})


@router.post("/llmasjudge/playground")
async def playground(request: Request) -> JSONResponse:
    payload: dict = {}
    try:
        payload = await request.json()
    except Exception:
        payload = {}

    receiptText = str(payload.get("receiptText", ""))[:5000]
    agentVerdict = str(payload.get("agentVerdict", "requiresReview"))
    if agentVerdict not in _VALID_VERDICTS:
        return JSONResponse({"error": "invalid agentVerdict"}, status_code=400)

    userJustification = str(payload.get("userJustification", ""))[:500]

    # Use the existing critique path as the ad-hoc judge (cheap, in-process).
    from agentic_claims.agents.compliance.critique import runSelfCritique

    try:
        result = await runSelfCritique(
            originalVerdict=agentVerdict,
            context={"receiptText": receiptText, "justification": userJustification},
        )
    except Exception as exc:
        logger.warning("/llmasjudge/playground critique error: %s", exc)
        return JSONResponse({"error": "critique unavailable"}, status_code=503)
    return JSONResponse(result)
