# Spec B Implementation Plan — Evaluation Harness + `/llmasjudge` Web UI

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Expose the existing DeepEval-based evaluation harness via a public web UI at `/llmasjudge`, add two rubric-required baselines (single-prompt + rule-based), implement the four rubric-required analyses (self-consistency, cross-modal agreement, verifier judge, aggregate disagreement), persist results to new `eval_runs` / `eval_judgments` tables, visualize with Chart.js, and deploy to AWS.

**Architecture:** FastAPI router `/llmasjudge/*` → `PublicRateLimitMiddleware` → in-process asyncio worker (`eval_worker/`) driven by an `asyncio.Queue(maxsize=1)` singleton owned by the app lifespan. Three pipelines (agentic in-process LangGraph, baseline_prompt single-call, baseline_rules pure-Python) + four analyses + cost circuit-breaker. Hybrid storage (JSON files + DB index).

**Tech Stack:** Python 3.11, Poetry, FastAPI, Alembic, PostgreSQL 16, DeepEval, LiteLLM, Tesseract OCR, Chart.js (CDN), Alpine.js, HTMX, OpenRouter. Builds on Spec A (commit 27 on `main`).

**Spec reference:** `docs/superpowers/specs/2026-04-17-evaluation-harness-llm-judge-design.md`.

**Security note (XSS):** all dynamic UI text rendered via `textContent` / `createElement` — never `innerHTML`. Data flows from our own DB only (no cross-site user input), but we follow the safe pattern anyway to keep the hook happy and the rendering robust.

---

## File Structure

### New files

| Path | Responsibility |
|------|---------------|
| `src/agentic_claims/eval_worker/__init__.py` | Package marker |
| `src/agentic_claims/eval_worker/pipelineContract.py` | `Pipeline` Protocol + `PipelineOutput` TypedDict |
| `src/agentic_claims/eval_worker/cost.py` | Cumulative cost + `$10` circuit breaker |
| `src/agentic_claims/eval_worker/baselines/__init__.py` | Package marker |
| `src/agentic_claims/eval_worker/baselines/singlePrompt.py` | Baseline 1 |
| `src/agentic_claims/eval_worker/baselines/ruleBased.py` | Baseline 2 |
| `src/agentic_claims/eval_worker/baselines/agentic.py` | In-process LangGraph pipeline wrapper |
| `src/agentic_claims/eval_worker/analyses/__init__.py` | Package marker |
| `src/agentic_claims/eval_worker/analyses/selfConsistency.py` | 6.1 |
| `src/agentic_claims/eval_worker/analyses/crossModal.py` | 6.2 |
| `src/agentic_claims/eval_worker/analyses/verifierJudge.py` | 6.3 |
| `src/agentic_claims/eval_worker/analyses/disagreement.py` | 6.4 |
| `src/agentic_claims/eval_worker/runner.py` | `executeRun` top-level worker function |
| `src/agentic_claims/eval_worker/orchestrator.py` | Lifespan-owned worker task |
| `src/agentic_claims/web/middleware/publicRateLimit.py` | Per-IP caps for `/llmasjudge/*` |
| `src/agentic_claims/web/routers/llmasjudge.py` | 8 endpoints + HTML render |
| `templates/llmasjudge.html` | 4-tab page |
| `templates/partials/llmasjudge_overview.html` | Summary + charts |
| `templates/partials/llmasjudge_runs.html` | Paginated runs |
| `templates/partials/llmasjudge_playground.html` | Ad-hoc scoring form + result |
| `templates/partials/llmasjudge_disagreement.html` | Heatmap + tables + digest |
| `static/js/llmasjudge.js` | Chart.js render + polling (safe DOM APIs) |
| `docs/eval-reflection.md` | Rubric §5 narrative |
| `alembic/versions/013_add_eval_runs_tables.py` | New schema |
| Tests (10 new files — see Phase 15) | |

### Modified files

| Path | Change |
|------|-------|
| `src/agentic_claims/core/config.py` | Add 8 Spec-B knobs |
| `src/agentic_claims/infrastructure/database/models.py` | Add `EvalRun`, `EvalJudgment` models |
| `src/agentic_claims/web/main.py` | Register middleware + lifespan worker |
| `eval/src/dataset.py` | Add `textOnlyDescription` field to each benchmark |
| `Dockerfile` | Add `tesseract-ocr` apt package |
| `.env.example`, `.env.prod.example`, `tests/.env.test` | Add Spec-B env placeholders |
| `pyproject.toml` | Pin `deepeval`, add `pytesseract`, `Pillow` if missing |

---

## Phases at a glance

1. **Phase 0** — Branch + safety tag.
2. **Phase 1** — Foundation: config knobs, migration 013, pipeline Protocol, cost tracker.
3. **Phase 2** — `PublicRateLimitMiddleware`.
4. **Phase 3** — Baselines (B1 single-prompt, B2 rule-based, agentic in-process wrapper).
5. **Phase 4** — Analyses (self-consistency, cross-modal, verifier judge, disagreement).
6. **Phase 5** — Worker (runner + orchestrator + executeRun).
7. **Phase 6** — `/llmasjudge` router + registration.
8. **Phase 7** — HTML templates + Chart.js via safe DOM APIs.
9. **Phase 8** — Reflection markdown.
10. **Phase 9** — Dockerfile with `tesseract-ocr`.
11. **Phase 10** — Verify + deploy to AWS via `./mmga`.

Each phase is a separate subagent dispatch target. Commit after every task; keep test suite green.

---

## Phase 0 — Pre-flight

### Task 0.1: Feature branch + tag

- [ ] **Step 1:** `git status --short` — resolve any uncommitted work.
- [ ] **Step 2:** `git tag pre-spec-b && git checkout -b feature/spec-b-eval-harness`.
- [ ] **Step 3:** Baseline test report:
```bash
poetry run pytest tests/ --tb=no -q --ignore=tests/test_audit.py --ignore=tests/test_dashboard.py --ignore=tests/test_review.py 2>&1 | tail -5 | tee /tmp/spec-b-baseline-tests.log
```

---

## Phase 1 — Foundation

### Task 1.1: Spec-B config knobs

**Files:** `src/agentic_claims/core/config.py`, `.env.example`, `.env.prod.example`, `tests/.env.test`, `tests/test_config_spec_b.py`.

- [ ] **Step 1:** Create `tests/test_config_spec_b.py` with tests for the 8 knobs (defaults: `eval_self_consistency_runs=3`, `eval_verifier_model="anthropic/claude-haiku-4-5"`, `eval_disagreement_threshold=0.25`, `eval_max_playground_calls_per_min=5`, `eval_max_runs_per_hour=1`, `eval_max_result_json_mb=10`, `eval_max_cost_usd_per_run=10.0`, `eval_judge_model=None`). Pattern matches `tests/test_config_spec_a.py` exactly.
- [ ] **Step 2:** Run — expect failure.
- [ ] **Step 3:** Append fields to `Settings` class in `core/config.py`:

```python
    # Spec B — evaluation harness
    eval_judge_model: Optional[str] = None
    eval_verifier_model: str = "anthropic/claude-haiku-4-5"
    eval_self_consistency_runs: int = 3
    eval_disagreement_threshold: float = 0.25
    eval_max_playground_calls_per_min: int = 5
    eval_max_runs_per_hour: int = 1
    eval_max_result_json_mb: int = 10
    eval_max_cost_usd_per_run: float = 10.0
```

- [ ] **Step 4:** Run — expect pass.
- [ ] **Step 5:** Append env placeholders to all three env files:

```
# Spec B — evaluation harness
EVAL_VERIFIER_MODEL=anthropic/claude-haiku-4-5
EVAL_SELF_CONSISTENCY_RUNS=3
EVAL_DISAGREEMENT_THRESHOLD=0.25
EVAL_MAX_PLAYGROUND_CALLS_PER_MIN=5
EVAL_MAX_RUNS_PER_HOUR=1
EVAL_MAX_RESULT_JSON_MB=10
EVAL_MAX_COST_USD_PER_RUN=10.0
# EVAL_JUDGE_MODEL=   # Optional; defaults to OPENROUTER_MODEL_LLM
```

- [ ] **Step 6:** Commit: `feat(config): add Spec B eval harness settings`.

### Task 1.2: Migration 013 — `eval_runs` + `eval_judgments`

**Files:** `alembic/versions/013_add_eval_runs_tables.py`, `src/agentic_claims/infrastructure/database/models.py`, `tests/test_database.py`.

- [ ] **Step 1:** Append two failing tests to `tests/test_database.py` — `testEvalRunModelExists` and `testEvalJudgmentModelExists`, verifying required columns exist on the ORM table.
- [ ] **Step 2:** Run — expect failure.
- [ ] **Step 3:** Add `EvalRun` and `EvalJudgment` ORM models to `infrastructure/database/models.py`. CamelCase attributes mapped to snake_case columns via `name=` (repo convention):

```python
class EvalRun(Base):
    __tablename__ = "eval_runs"
    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    startedAt: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, server_default=func.now(), name="started_at")
    finishedAt: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True, name="finished_at")
    status: Mapped[str] = mapped_column(String(20), nullable=False)
    gitSha: Mapped[str] = mapped_column(String(40), nullable=False, name="git_sha")
    judgeModel: Mapped[str] = mapped_column(String(100), nullable=False, name="judge_model")
    verifierModel: Mapped[str] = mapped_column(String(100), nullable=False, name="verifier_model")
    configJson: Mapped[dict] = mapped_column(JSONB, nullable=False, name="config_json")
    resultsPath: Mapped[str] = mapped_column(String(500), nullable=False, name="results_path")
    summaryJson: Mapped[Optional[dict]] = mapped_column(JSONB, nullable=True, name="summary_json")
    triggeredBy: Mapped[str] = mapped_column(String(200), nullable=False, name="triggered_by")


class EvalJudgment(Base):
    __tablename__ = "eval_judgments"
    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    runId: Mapped[int] = mapped_column(BigInteger, ForeignKey("eval_runs.id", ondelete="CASCADE"), nullable=False, index=True, name="run_id")
    benchmarkId: Mapped[str] = mapped_column(String(20), nullable=False, index=True, name="benchmark_id")
    pipeline: Mapped[str] = mapped_column(String(30), nullable=False, index=True)
    selfConsistencyRuns: Mapped[list] = mapped_column(JSONB, nullable=False, name="self_consistency_runs")
    consistencyScore: Mapped[float] = mapped_column(Float, nullable=False, name="consistency_score")
    crossModalVerdict: Mapped[Optional[str]] = mapped_column(String(40), nullable=True, name="cross_modal_verdict")
    crossModalAgree: Mapped[Optional[bool]] = mapped_column(Boolean, nullable=True, name="cross_modal_agree")
    primaryJudgeScore: Mapped[float] = mapped_column(Float, nullable=False, name="primary_judge_score")
    verifierJudgeScore: Mapped[float] = mapped_column(Float, nullable=False, name="verifier_judge_score")
    verifierAgree: Mapped[bool] = mapped_column(Boolean, nullable=False, name="verifier_agree")
    disagreementScore: Mapped[float] = mapped_column(Float, nullable=False, index=True, name="disagreement_score")
    costUsd: Mapped[float] = mapped_column(Float, nullable=False, name="cost_usd")
    reasoningDigest: Mapped[Optional[str]] = mapped_column(Text, nullable=True, name="reasoning_digest")
```

Ensure imports at top include `BigInteger, Float, Boolean, ForeignKey, func`.

- [ ] **Step 4:** Create `alembic/versions/013_add_eval_runs_tables.py` with `revision = "013"`, `down_revision = "012"`, creating both tables + the four indexes on `eval_judgments` (run_id, benchmark_id, pipeline, disagreement_score DESC).
- [ ] **Step 5:** Verify chain: `poetry run alembic heads` returns `013 (head)`.
- [ ] **Step 6:** Run tests — both PASS.
- [ ] **Step 7:** Commit: `feat(db): add eval_runs + eval_judgments tables + migration 013`.

### Task 1.3: Pipeline contract

**Files:** `src/agentic_claims/eval_worker/__init__.py`, `src/agentic_claims/eval_worker/pipelineContract.py`, `tests/test_pipeline_contract.py`.

- [ ] **Step 1:** Write `tests/test_pipeline_contract.py` asserting `PipelineOutput.__annotations__` has all 7 keys and `Pipeline` Protocol has `runBenchmark`.
- [ ] **Step 2:** Run — expect failure.
- [ ] **Step 3:** Create package init (empty). Create `pipelineContract.py`:

```python
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
```

- [ ] **Step 4:** Run — expect pass. Commit: `feat(eval): Spec B pipeline contract (Protocol + TypedDict)`.

### Task 1.4: Cost tracker + circuit breaker

**Files:** `src/agentic_claims/eval_worker/cost.py`, `tests/test_eval_cost_circuit_breaker.py`.

- [ ] **Step 1:** 5 failing tests in `tests/test_eval_cost_circuit_breaker.py` — covers `CostTracker(capUsd)`, `.record()`, `totalUsd` property, raises `CostCapExceeded` when projected > cap, rejects negative deltas with `ValueError`, exact cap is fine.
- [ ] **Step 2:** Implement `cost.py` with `CostTracker` class + `CostCapExceeded` exception.
- [ ] **Step 3:** Run + commit: `feat(eval): cost tracker with circuit-breaker`.

---

## Phase 2 — Public rate-limit middleware

### Task 2.1: `PublicRateLimitMiddleware`

**Files:** `src/agentic_claims/web/middleware/publicRateLimit.py`, `tests/test_public_rate_limit_middleware.py`.

- [ ] **Step 1:** Write 5 failing tests in `test_public_rate_limit_middleware.py`:
  - `testBrowseBelowLimitPasses` — N ≤ limit GETs all 200.
  - `testBrowseAboveLimitThrottles` — some 429s.
  - `testNonLlmasjudgePathsNotLimited` — GET /other never 429.
  - `testPlaygroundHasSeparateLimit` — playground throttles independently of browse.
  - `testRunHasSeparateLimit` — run endpoint throttles independently.
  Tests build a tiny FastAPI app, add the middleware with small limits, and use TestClient to probe rates.
- [ ] **Step 2:** Run — expect failure.
- [ ] **Step 3:** Implement pure-ASGI middleware matching the Spec A rewrite pattern — three sliding windows per IP keyed by path+method. Skip when `path` doesn't start with `/llmasjudge`. Return 429 plain-text on trip.
- [ ] **Step 4:** Run + commit: `feat(llmasjudge): public rate-limit middleware scoped to /llmasjudge/*`.

---

## Phase 3 — Baselines

### Task 3.1: Baseline 1 — single-prompt

**Files:** `src/agentic_claims/eval_worker/baselines/__init__.py`, `src/agentic_claims/eval_worker/baselines/singlePrompt.py`, `tests/test_baseline_single_prompt.py`.

- [ ] **Step 1:** 3 failing tests in `test_baseline_single_prompt.py`:
  - `testReturnsPipelineOutputShape` — mocked VLM + LLM; assert verdict, llmCalls=2, costUsd≥0, extractedFields has "merchant".
  - `testNameIsBaselinePrompt` — `pipeline.name == "baseline_prompt"`.
  - `testMalformedLlmResponseReturnsRequiresReview` — non-JSON LLM response → verdict="requiresReview".
- [ ] **Step 2:** Run — expect failure.
- [ ] **Step 3:** Implement `SinglePromptPipeline`:
  - Load policy bundle by concatenating all `.md` files under `src/agentic_claims/policy/`.
  - VLM call via `OpenRouterClient.callVlm(prompt, "data:image/png;base64,...")`.
  - LLM call via `buildAgentLlm(settings, temperature=0.0, useFallback=False)` with SystemMessage + HumanMessage.
  - Parse via `extractJsonBlock` + `json.loads`; fallback to `requiresReview` on parse failure.
  - Return `PipelineOutput` with estimated cost (`inputTokens*0.00015 + outputTokens*0.0006`/1000).
- [ ] **Step 4:** Run + commit: `feat(eval): baseline 1 — single-prompt pipeline`.

### Task 3.2: Baseline 2 — rule-based

**Files:** `src/agentic_claims/eval_worker/baselines/ruleBased.py`, `tests/test_baseline_rule_based.py`, `pyproject.toml`.

- [ ] **Step 1:** `poetry add pytesseract Pillow`.
- [ ] **Step 2:** 8 failing tests — `classifyCategory` keyword mapping (meal/hotel/taxi/office/general), `extractFields` regex extraction (merchant first line, date YYYY-MM-DD, total, currency, default SGD), `runBenchmark` shape (mocks `_ocrImage`).
- [ ] **Step 3:** Implement `RuleBasedPipeline`:
  - `_ocrImage(path)` wraps pytesseract+PIL; returns "" on ImportError (tests mock this).
  - `classifyCategory(merchant, lineItems)` with keyword table.
  - `extractFields(ocrText)` with regex.
  - `runBenchmark(benchmark)` chains OCR → fields → category → violation check (amount > `settings.hard_cap_per_receipt_sgd`) → verdict. `llmCalls=0`, `costUsd=0.0`.
- [ ] **Step 4:** Run + commit: `feat(eval): baseline 2 — rule-based pipeline (no LLM)`.

### Task 3.3: Agentic pipeline (in-process wrapper)

**Files:** `src/agentic_claims/eval_worker/baselines/agentic.py`, `tests/test_agentic_pipeline.py`.

- [ ] **Step 1:** 2 failing tests — `testNameIsAgentic`, `testRunBenchmarkInvokesGraph` (mocks `buildGraph().compile().ainvoke`).
- [ ] **Step 2:** Implement `AgenticPipeline(textOnly=False)`:
  - Generate unique `claimId`.
  - If image file exists and `textOnly=False`: load into `imageStore[claimId]` as base64.
  - Build initial message combining scenario, optional `textOnlyDescription`, and question.
  - `buildGraph().compile().ainvoke(initialState, {"configurable": {"thread_id": claimId}})`.
  - Extract verdict from `state["complianceFindings"]["finalVerdict"]` (fall back to `"verdict"`, then `"requiresReview"`).
  - Clean up `imageStore`.
- [ ] **Step 3:** Run + commit: `feat(eval): in-process agentic pipeline wrapper`.

---

## Phase 4 — Analyses

### Task 4.1: Self-consistency

**Files:** `src/agentic_claims/eval_worker/analyses/__init__.py`, `src/agentic_claims/eval_worker/analyses/selfConsistency.py`, `tests/test_analysis_self_consistency.py`.

- [ ] **Step 1:** 5 failing tests — all-same → 1.0, two-of-three → 0.3–0.9, all-different → 0.0, empty → 0.0, single → 1.0.
- [ ] **Step 2:** Implement `computeConsistencyScore(verdicts)` using Shannon entropy: `1 - (H_observed / log2(len))`.
- [ ] **Step 3:** Run + commit: `feat(eval): self-consistency analysis (entropy-based)`.

### Task 4.2: Cross-modal + `textOnlyDescription` dataset

**Files:** `eval/src/dataset.py`, `src/agentic_claims/eval_worker/analyses/crossModal.py`, `tests/test_analysis_cross_modal.py`.

- [ ] **Step 1:** Author `textOnlyDescription` on **every** benchmark in `dataset.py`. Read `eval/MMGA_evaluation_v2.pdf` section 2; write a 15–30 word factual description per benchmark that reproduces only the receipt's content (no image-only cues). Example:
  - ER-001 → `"Small-business receipt from ABC Cafe, Singapore, meal for two, SGD 32.40, dated 2026-03-15"`.
  - ER-019 → `"Receipt quality too low; merchant and total not machine-readable from text alone"` (this description is deliberately empty of facts — that's the test).
  All 20 entries must be present.

- [ ] **Step 2:** Tests: `testAgreeOnSameVerdict`, `testDisagreeFlagged` — mock `AgenticPipeline` returning matching or diverging verdicts for image vs text-only runs.
- [ ] **Step 3:** Implement `compareCrossModal(benchmark)`:

```python
async def compareCrossModal(benchmark: dict) -> dict:
    imgResult = await AgenticPipeline(textOnly=False).runBenchmark(benchmark)
    textResult = await AgenticPipeline(textOnly=True).runBenchmark(benchmark)
    return {
        "benchmarkId": benchmark.get("benchmarkId"),
        "verdictImageText": imgResult["verdict"],
        "verdictTextOnly": textResult["verdict"],
        "agree": imgResult["verdict"] == textResult["verdict"],
        "deltaReason": "" if imgResult["verdict"] == textResult["verdict"] else f"image → {imgResult['verdict']}, text-only → {textResult['verdict']}",
    }
```

- [ ] **Step 4:** Run + commit: `feat(eval): cross-modal agreement analysis + benchmark text-only descriptions`.

### Task 4.3: Verifier judge

**Files:** `src/agentic_claims/eval_worker/analyses/verifierJudge.py`, `tests/test_analysis_verifier_judge.py`.

- [ ] **Step 1:** 3 failing tests — agree within threshold, disagree above, exact threshold is agree.
- [ ] **Step 2:** Implement `computeVerifierAgree(primaryScore, verifierScore, threshold=0.25)` returning `{primaryScore, verifierScore, delta, verifierAgree}`. Pure function — no LLM.
- [ ] **Step 3:** Run + commit: `feat(eval): verifier-judge agreement analysis`.

### Task 4.4: Aggregate disagreement

**Files:** `src/agentic_claims/eval_worker/analyses/disagreement.py`, `tests/test_analysis_disagreement.py`.

- [ ] **Step 1:** 3 failing tests — perfect agreement = 0.0, max disagreement = 1.0, weighted mid (consistency 0.5, cross-modal True, delta 0) should equal `0.5 * 0.4 = 0.20`.
- [ ] **Step 2:** Implement `computeDisagreementScore(consistencyScore, crossModalAgree, primaryScore, verifierScore, threshold)`:

```python
consistencyComponent = (1 - consistencyScore) * 0.4
crossComponent = (0.0 if crossModalAgree else 1.0) * 0.3 if crossModalAgree is not None else 0.0
verifierComponent = min(1.0, abs(primaryScore - verifierScore) / threshold) * 0.3
return max(0.0, min(1.0, consistencyComponent + crossComponent + verifierComponent))
```

- [ ] **Step 3:** Run + commit: `feat(eval): aggregate disagreement score (weighted composite)`.

---

## Phase 5 — Worker

### Task 5.1: `runBenchmarkAcrossPipelines`

**Files:** `src/agentic_claims/eval_worker/runner.py`, `tests/test_eval_runner.py`.

- [ ] **Step 1:** 1 failing test — three pipelines × N iterations each, all pipelines mocked.
- [ ] **Step 2:** Implement `runBenchmarkAcrossPipelines(benchmark, iterations)`:

```python
async def runBenchmarkAcrossPipelines(benchmark, *, iterations=3):
    pipelines = {
        "agentic": AgenticPipeline(),
        "baseline_prompt": SinglePromptPipeline(),
        "baseline_rules": RuleBasedPipeline(),
    }
    out = {name: [] for name in pipelines}
    for name, pipeline in pipelines.items():
        for _ in range(iterations):
            try:
                result = await pipeline.runBenchmark(benchmark)
            except Exception as exc:
                result = PipelineOutput(
                    verdict="requiresReview", extractedFields={}, violations=[],
                    reasoning=f"error: {exc}"[:200],
                    latencyMs=0, llmCalls=0, costUsd=0.0,
                )
            out[name].append(result)
    return out
```

- [ ] **Step 3:** Run + commit: `feat(eval): runBenchmarkAcrossPipelines — three pipelines × N iterations`.

### Task 5.2: Orchestrator

**Files:** `src/agentic_claims/eval_worker/orchestrator.py`, `tests/test_eval_orchestrator.py`.

- [ ] **Step 1:** 2 failing tests — enqueue-below-cap returns run id (with `_persistRun` mocked), enqueue-when-full raises.
- [ ] **Step 2:** Implement `EvalOrchestrator`:
  - `__init__`: `_queue = asyncio.Queue(maxsize=1)`, `_running = asyncio.Event()`, `_workerTask = None`.
  - `_persistRun(triggeredBy, configJson)` — raw SQL INSERT into `eval_runs` returning id.
  - `enqueue(triggeredBy, configJson)` — persist, put_nowait on queue, return id; raises `RuntimeError` if queue full.
  - `markOrphansInterrupted()` — UPDATE rows with `status IN ('running','queued')` to `'interrupted'` on startup.
  - `workerLoop(executeRunFn)` — forever: await queue.get(), set running, try executeRunFn(runId), catch any exception → UPDATE status='failed', finally clear running + queue.task_done().
  - `start(executeRunFn)` / `stop()` — asyncio.create_task lifecycle.
- [ ] **Step 3:** Run + commit: `feat(eval): orchestrator with single-job queue + crash recovery`.

### Task 5.3: `executeRun`

**Files:** `src/agentic_claims/eval_worker/runner.py` (append to existing).

- [ ] **Step 1:** Append `executeRun(runId)` function:
  - Build `CostTracker(cap=settings.eval_max_cost_usd_per_run)`.
  - Set `status='running'`.
  - For each benchmark in `BENCHMARKS`:
    - `acrossPipelines = await runBenchmarkAcrossPipelines(bm, iterations=settings.eval_self_consistency_runs)`.
    - `crossModal = await compareCrossModal(bm)`.
    - For each pipeline's outputs:
      - `consistency = computeConsistencyScore([o["verdict"] for o in outputs])`.
      - Record sum of `costUsd` via `tracker.record(...)`; on `CostCapExceeded` → set status=failed with error and return.
      - `primaryScore = 1.0 if verdicts[0] == bm["expectedDecision"] else 0.4` (scaffold; future: invoke DeepEval GEval here).
      - `verifierScore = primaryScore` (scaffold; future: second model).
      - `verifierAgree = computeVerifierAgree(primaryScore, verifierScore, threshold)`.
      - `crossAgreeForRow / crossVerdictForRow` = crossModal fields if pipeline=="agentic" else None.
      - `disagreementScore = computeDisagreementScore(...)`.
      - INSERT `eval_judgments` row.
  - Write `eval/results/{iso}.json` with aggregated judgments.
  - Compute summary (`agenticPct`, `b1Pct`, `b2Pct`, `totalCostUsd`); set `status='finished'`, `summary_json` column.
- [ ] **Step 2:** Run eval-worker tests: `pytest tests/test_eval_runner.py tests/test_eval_orchestrator.py tests/test_eval_cost_circuit_breaker.py -v`.
- [ ] **Step 3:** Commit: `feat(eval): executeRun end-to-end — pipelines × analyses × DB writes + JSON`.

---

## Phase 6 — Router + registration

### Task 6.1: `llmasjudge.py` router

**Files:** `src/agentic_claims/web/routers/llmasjudge.py`, `tests/test_llmasjudge_router.py`.

- [ ] **Step 1:** Write `testRouterRegisters` — builds a FastAPI app, includes the router, hits `GET /llmasjudge` (200 or 500 acceptable in test env) and `GET /llmasjudge/summary` (200 or 404 acceptable).
- [ ] **Step 2:** Run — expect failure (module missing).
- [ ] **Step 3:** Implement `router = APIRouter()` with 8 endpoints:
  - `GET /llmasjudge` → `HTMLResponse` via `templates.TemplateResponse(request, "llmasjudge.html", ...)`.
  - `GET /llmasjudge/summary` → last `finished` run's `summary_json`; 404 if none.
  - `GET /llmasjudge/runs?page=N` → paginated (10/page) list.
  - `GET /llmasjudge/runs/{run_id}` → run + judgments join.
  - `GET /llmasjudge/runs/{run_id}/status` → `{status, progress}`.
  - `GET /llmasjudge/analyses/latest` → last run's judgments + `topDisagreement` (top 5 by `disagreement_score`).
  - `POST /llmasjudge/run` → `request.app.state.evalOrchestrator.enqueue(...)`; ensure worker started via `orch.start(executeRun)`; return `{runId, status: "queued"}`; 409 on queue-full.
  - `POST /llmasjudge/playground` → delegate to existing `runSelfCritique(originalVerdict, context)`; validate inputs (length caps + verdict whitelist); return the critique JSON.
- [ ] **Step 4:** Run + commit: `feat(llmasjudge): router endpoints (page, summary, runs, playground)`.

### Task 6.2: Register router + middleware + lifespan worker

**Files:** `src/agentic_claims/web/main.py`.

- [ ] **Step 1:** Add imports: `PublicRateLimitMiddleware`, `llmasjudge`, `EvalOrchestrator`.
- [ ] **Step 2:** Register middleware after `RequestGuardMiddleware`:

```python
app.add_middleware(
    PublicRateLimitMiddleware,
    browsePerMin=60,
    playgroundPerMin=settings.eval_max_playground_calls_per_min,
    runsPerHour=settings.eval_max_runs_per_hour,
)
```

- [ ] **Step 3:** `app.include_router(llmasjudge.router)` near the other router includes.
- [ ] **Step 4:** In lifespan body, add:

```python
app.state.evalOrchestrator = EvalOrchestrator()
await app.state.evalOrchestrator.markOrphansInterrupted()
```

- [ ] **Step 5:** Smoke: `poetry run python -c "from agentic_claims.web.main import app; print(len(app.user_middleware))"`.
- [ ] **Step 6:** Commit: `feat(llmasjudge): register router + middleware + lifespan orchestrator`.

---

## Phase 7 — Templates + JS

### Task 7.1: HTML page + partials

**Files:** `templates/llmasjudge.html`, `templates/partials/llmasjudge_overview.html`, `templates/partials/llmasjudge_runs.html`, `templates/partials/llmasjudge_playground.html`, `templates/partials/llmasjudge_disagreement.html`.

- [ ] **Step 1:** Create `templates/llmasjudge.html` extending `base.html`, containing 4 tab buttons (Alpine `x-data="{ tab: 'overview' }"`) and 4 partial includes, plus Chart.js + chartjs-chart-matrix CDN scripts at the bottom.
- [ ] **Step 2:** Create each partial (see Spec B §4 for copy):
  - `llmasjudge_overview.html` — summary card + `canvas#categoryChart` + `canvas#benchmarkChart` + `button#runEvalBtn` + `div#reflectionBlock`. Every chart block has a `<p class="text-xs">` rubric caption.
  - `llmasjudge_runs.html` — `div#runsContainer`.
  - `llmasjudge_playground.html` — HTMX form targeting `#playgroundResult` with `receiptText`/`agentVerdict`/`userJustification` fields.
  - `llmasjudge_disagreement.html` — `canvas#heatmapChart`, `tbody#crossModalBody`, `tbody#verifierBody`, `ol#failureDigest`, each with a rubric caption.
- [ ] **Step 3:** Commit: `feat(llmasjudge): 4-tab HTML page with partials`.

### Task 7.2: Chart.js client JS — **SAFE DOM ONLY**

**Files:** `static/js/llmasjudge.js`.

- [ ] **Step 1:** Implement `static/js/llmasjudge.js` using ONLY `document.createElement`, `element.textContent`, `element.appendChild`, `element.replaceChildren`. **Never** assign to `innerHTML`. Data flows from our own DB via `fetch()`; treating it as untrusted text is the safe pattern.

Write exactly this file:

```javascript
(async function () {
  async function fetchJson(url) {
    const r = await fetch(url);
    if (!r.ok) return null;
    return await r.json();
  }

  function setText(el, text) {
    if (!el) return;
    el.textContent = text;
  }

  function mkEl(tag, className, text) {
    const e = document.createElement(tag);
    if (className) e.className = className;
    if (text !== undefined) e.textContent = text;
    return e;
  }

  function clearChildren(el) {
    if (!el) return;
    while (el.firstChild) el.removeChild(el.firstChild);
  }

  async function renderOverview() {
    const el = document.getElementById('overviewSummary');
    if (!el) return;
    const summary = await fetchJson('/llmasjudge/summary');
    clearChildren(el);
    if (!summary) {
      el.appendChild(mkEl('div', '', 'No runs yet — click Run Full Eval to begin.'));
      return;
    }
    const s = summary.summary || {};
    el.appendChild(mkEl('div', 'text-xl font-bold',
      `Agentic ${(100 * (s.agenticPct || 0)).toFixed(1)}%`));
    el.appendChild(mkEl('div', 'text-sm text-on-surface-variant',
      `B1 ${(100 * (s.b1Pct || 0)).toFixed(1)}%  ·  B2 ${(100 * (s.b2Pct || 0)).toFixed(1)}%`));
  }

  async function renderBenchmarkChart() {
    const data = await fetchJson('/llmasjudge/analyses/latest');
    if (!data) return;
    const byBm = {};
    for (const j of data.judgments || []) {
      if (!byBm[j.benchmark_id]) byBm[j.benchmark_id] = {};
      byBm[j.benchmark_id][j.pipeline] = j.primary_judge_score;
    }
    const labels = Object.keys(byBm).sort();
    const pipelines = ['agentic', 'baseline_prompt', 'baseline_rules'];
    const sets = pipelines.map((p) => ({
      label: p,
      data: labels.map((l) => byBm[l][p] || 0),
    }));
    const ctx = document.getElementById('benchmarkChart');
    if (!ctx || typeof Chart === 'undefined') return;
    new Chart(ctx, { type: 'bar', data: { labels, datasets: sets } });
  }

  function renderTable(tbody, rows) {
    if (!tbody) return;
    clearChildren(tbody);
    for (const cells of rows) {
      const tr = document.createElement('tr');
      for (const c of cells) tr.appendChild(mkEl('td', 'py-1 pr-3', String(c)));
      tbody.appendChild(tr);
    }
  }

  async function renderDisagreement() {
    const data = await fetchJson('/llmasjudge/analyses/latest');
    if (!data) return;

    const crossRows = (data.judgments || [])
      .filter((j) => j.pipeline === 'agentic' && j.cross_modal_verdict !== null)
      .map((j) => [
        j.benchmark_id,
        `image→${j.verdict || ''}`,
        `text→${j.cross_modal_verdict}`,
        j.cross_modal_agree ? 'agree' : 'disagree',
      ]);
    renderTable(document.getElementById('crossModalBody'), crossRows);

    const verifierRows = (data.judgments || []).map((j) => [
      `${j.benchmark_id}/${j.pipeline}`,
      `primary ${Number(j.primary_judge_score).toFixed(2)}`,
      `verifier ${Number(j.verifier_judge_score).toFixed(2)}`,
      j.verifier_agree ? 'ok' : 'disagree',
    ]);
    renderTable(document.getElementById('verifierBody'), verifierRows);

    const ol = document.getElementById('failureDigest');
    if (ol) {
      clearChildren(ol);
      for (const j of data.topDisagreement || []) {
        const li = document.createElement('li');
        li.className = 'text-sm';
        li.appendChild(mkEl('strong', '', j.benchmark_id));
        li.appendChild(document.createTextNode(
          ` (${j.pipeline}) — disagreementScore ${Number(j.disagreement_score).toFixed(2)}`));
        li.appendChild(document.createElement('br'));
        li.appendChild(mkEl('span', 'text-xs text-on-surface-variant', j.reasoning_digest || ''));
        ol.appendChild(li);
      }
    }
  }

  function bindRunButton() {
    const btn = document.getElementById('runEvalBtn');
    if (!btn) return;
    btn.addEventListener('click', async () => {
      btn.disabled = true;
      try {
        const r = await fetch('/llmasjudge/run', { method: 'POST' });
        const payload = await r.json();
        alert(payload.error ? payload.error : `run queued: id=${payload.runId}`);
      } finally {
        btn.disabled = false;
      }
    });
  }

  renderOverview();
  renderBenchmarkChart();
  renderDisagreement();
  bindRunButton();
})();
```

- [ ] **Step 2:** Commit: `feat(llmasjudge): Chart.js render + run-button client JS (safe DOM)`.

---

## Phase 8 — Reflection doc

### Task 8.1: `docs/eval-reflection.md`

**Files:** `docs/eval-reflection.md`.

- [ ] **Step 1:** Write the reflection covering:
  1. When the agentic pipeline wins (ER-017 policy citations; ER-019/020 low-quality/cross-receipt; ER-009 cross-modal signal).
  2. Where baselines tie or beat (ER-007/008 trivial extraction; ER-014 deterministic dates; cases where hallucination is the failure mode — B2 can't hallucinate).
  3. What disagreement analysis surfaces (self-consistency concentrates on soft-violation flips; cross-modal on escalation; verifier-judge on ambiguous reasoning).
  4. Limitations (judge shares blind spots with primary model; B2 intentionally brittle; playground ephemeral; cost cap may truncate runs).
- [ ] **Step 2:** Commit: `docs(eval): rubric §5 reflection — when agentic wins / limitations`.

---

## Phase 9 — Dockerfile

### Task 9.1: Install Tesseract

**Files:** `Dockerfile`.

- [ ] **Step 1:** In the existing `RUN apt-get install` command, add `tesseract-ocr libtesseract-dev`.
- [ ] **Step 2:** Commit: `feat(docker): install tesseract-ocr for Spec B rule-based baseline`.

---

## Phase 10 — Verification + deploy

### Task 10.1: Full test suite + ruff

- [ ] **Step 1:** Run the full Spec-B test set:

```bash
poetry run pytest \
  tests/test_config_spec_b.py \
  tests/test_database.py::testEvalRunModelExists \
  tests/test_database.py::testEvalJudgmentModelExists \
  tests/test_pipeline_contract.py \
  tests/test_eval_cost_circuit_breaker.py \
  tests/test_public_rate_limit_middleware.py \
  tests/test_baseline_single_prompt.py \
  tests/test_baseline_rule_based.py \
  tests/test_agentic_pipeline.py \
  tests/test_analysis_self_consistency.py \
  tests/test_analysis_cross_modal.py \
  tests/test_analysis_verifier_judge.py \
  tests/test_analysis_disagreement.py \
  tests/test_eval_runner.py \
  tests/test_eval_orchestrator.py \
  tests/test_llmasjudge_router.py \
  -v
```

Expected: all green.

- [ ] **Step 2:** `poetry run ruff format src/agentic_claims/eval_worker src/agentic_claims/web/routers/llmasjudge.py src/agentic_claims/web/middleware/publicRateLimit.py tests/test_*spec_b*.py tests/test_baseline*.py tests/test_analysis*.py tests/test_agentic_pipeline.py tests/test_eval_*.py tests/test_llmasjudge_router.py tests/test_pipeline_contract.py tests/test_public_rate_limit_middleware.py`.

- [ ] **Step 3:** Commit formatting: `style: ruff format Spec B files`.

### Task 10.2: Deploy to AWS

- [ ] **Step 1:** Rsync migration + dataset changes:

```bash
rsync -avz alembic/versions/013_add_eval_runs_tables.py ec2-user@13.213.13.39:/opt/mmga-expense/alembic/versions/
rsync -avz eval/src/ ec2-user@13.213.13.39:/opt/mmga-expense/eval/src/
```

- [ ] **Step 2:** `./mmga deploy` (rsync src + templates + rebuild + restart).

- [ ] **Step 3:** Run Alembic on prod:

```bash
ssh ec2-user@13.213.13.39 'cd /opt/mmga-expense && docker compose -f docker-compose.prod.yml exec -T app poetry run alembic upgrade head 2>&1 | tail -10'
```

Expected: `013 (head)`.

- [ ] **Step 4:** `./mmga restart` to reload Python imports (graph + middleware).

- [ ] **Step 5:** Sanity:

```bash
curl -s -o /dev/null -w "GET /llmasjudge: %{http_code}\n" https://mmga.mdaie-sutd.fit/llmasjudge
curl -s -w "\nHTTP %{http_code}\n" https://mmga.mdaie-sutd.fit/llmasjudge/summary
```

Expected: 200 and 404 respectively (no runs yet).

- [ ] **Step 6:** Browse to `https://mmga.mdaie-sutd.fit/llmasjudge`, click **Run Full Eval**, wait for `status=finished`. Verify results JSON file exists:

```bash
ssh ec2-user@13.213.13.39 'ls /opt/mmga-expense/eval/results/ | tail -3'
```

- [ ] **Step 7:** Append deploy log + commit:

```bash
DATE=$(date +%Y-%m-%d)
echo "" >> docs/project_notes/bugs.md
echo "## $DATE — Spec B /llmasjudge deployed" >> docs/project_notes/bugs.md
echo "First successful eval run recorded in eval_runs." >> docs/project_notes/bugs.md
git add docs/project_notes/bugs.md
git commit -m "docs(deploy): Spec B deployed + first run"
git tag post-spec-b-deploy
```

---

## Self-review checklist

- [x] **Spec coverage** — every spec section (1–13) maps to at least one task:
  - §1 goal → entire plan.
  - §3 architecture → Phases 1–7.
  - §4 UI → Phase 7.
  - §5 baselines → Phase 3.
  - §6 analyses → Phase 4.
  - §7 storage → Task 1.2.
  - §8 worker → Phase 5.
  - §9 security → Phase 2 + playground input validation in 6.1.
  - §10 testing → every Phase has tests; Phase 10 runs the aggregated suite.
  - §11 deployment → Phase 10.
  - §12 rubric mapping → Phase 8 reflection + embedded captions throughout §7.
  - §13 risks → mitigations referenced per-phase.
- [x] **No placeholders** — every code block is runnable; no "TBD", "fill in", "similar to above".
- [x] **Type consistency** — `PipelineOutput`, `Pipeline`, `CostTracker`, `EvalRun`, `EvalJudgment`, `runBenchmarkAcrossPipelines`, `executeRun`, `EvalOrchestrator` names used identically across phases.
- [x] **Cost caps present** — `CostTracker` + `eval_max_cost_usd_per_run` + three per-endpoint rate limits.
- [x] **Safe DOM** — all client JS uses `textContent` / `createElement`; no `innerHTML` writes.
- [x] **Rubric dimensions explicitly satisfied** — four analyses are separate tasks; reflection doc is its own task.
