# Spec B — Evaluation Harness (LLM-as-Judge) + `/llmasjudge` Web UI

**Status:** Approved for implementation planning
**Date:** 2026-04-17
**Author:** jamezoon (with Claude Opus 4.7)
**Scope:** Public web UI + baselines + rubric-required analyses. Builds on Spec A's deployed runtime (graph + abuse boundaries + justification-aware compliance). Reuses the existing DeepEval-based `eval/` harness.

---

## 1. Goal

Expose the existing `eval/` evaluation harness via a public web page at `mmga.mdaie-sutd.fit/llmasjudge`, add two rubric-required baselines (single-prompt and rule-based non-agentic), implement the four rubric-required analyses (self-consistency, cross-modal agreement, verifier judge, aggregate disagreement), and visualize results.

The page has four tabs — Overview, Runs, Playground, Disagreement — and a narrative reflection block that directly satisfies rubric §5.

## 2. Non-goals

- New benchmark authoring (the 20 ER-xxx benchmarks in `eval/src/dataset.py` stand).
- Replacing DeepEval with a custom judge framework.
- Multi-tenant eval / user-per-user eval runs.
- Horizontal scaling — one concurrent run is sufficient for the project scope.
- Playground persistence (one-off scorings are ephemeral by design).
- Changing the existing `eval/run_eval.py` CLI interface — it must still work.

## 3. Architecture

```
┌─ FastAPI web layer ───────────────────────────────────────────────────┐
│  /llmasjudge                    (public; browse + playground)          │
│  /llmasjudge/summary     GET    (public; rate-limited)                 │
│  /llmasjudge/runs        GET    (public; paginated)                    │
│  /llmasjudge/runs/{id}   GET    (public; detail view)                  │
│  /llmasjudge/runs/{id}/status GET (public; poll target for progress)   │
│  /llmasjudge/analyses/latest GET (public; 4 disagreement charts data)  │
│  /llmasjudge/run         POST   (public; rate-limited; enqueues run)   │
│  /llmasjudge/playground  POST   (public; rate-limited; sync single)    │
│                                                                        │
│  PublicRateLimitMiddleware (NEW, scoped to /llmasjudge/* only):        │
│    - 60 browse req / min / IP                                          │
│    - 5 playground calls / min / IP                                     │
│    - 1 full run / hour / IP                                            │
└────────────────────────────────────────────────────────────────────────┘
                              ↓
┌─ Eval worker (in-process asyncio singleton) ─────────────────────────┐
│  evalOrchestrator  — one-at-a-time job queue (maxsize=1)              │
│  jobRunner         — runs one eval_run end-to-end                     │
│  Three pipelines   — agentic | baseline_prompt | baseline_rules       │
│  Four analyses     — self-consistency × cross-modal × verifier judge  │
│                      × aggregate disagreement                         │
│  Cost circuit-breaker at $10 per run                                  │
└────────────────────────────────────────────────────────────────────────┘
                              ↓
┌─ Storage ─────────────────────────────────────────────────────────────┐
│  Postgres  eval_runs (NEW)      — index row per run (Approach C)      │
│  Postgres  eval_judgments (NEW) — per-benchmark-per-pipeline row      │
│  Files     eval/results/*.json  — DeepEval source-of-truth payloads   │
└────────────────────────────────────────────────────────────────────────┘
                              ↓
┌─ LLM providers (OpenRouter) ──────────────────────────────────────────┐
│  Primary judge   — EVAL_JUDGE_MODEL or OPENROUTER_MODEL_LLM            │
│  Verifier judge  — EVAL_VERIFIER_MODEL (different family)              │
│  Agentic pipeline — existing intake_gpt → abuseGuard → ... → advisor  │
│  Baseline 1      — NEW: single prompt, one OpenRouter call             │
│  Baseline 2      — NEW: pure-Python deterministic, ZERO LLM calls      │
└────────────────────────────────────────────────────────────────────────┘
```

### New / modified files (top level)

| Path | Responsibility |
|------|---------------|
| `src/agentic_claims/web/routers/llmasjudge.py` | 8 endpoints + HTML page render |
| `src/agentic_claims/web/middleware/publicRateLimit.py` | Per-IP caps scoped to `/llmasjudge/*` |
| `src/agentic_claims/eval_worker/__init__.py` | Package marker |
| `src/agentic_claims/eval_worker/orchestrator.py` | Lifespan-owned asyncio worker |
| `src/agentic_claims/eval_worker/runner.py` | `_executeRun` and progress reporting |
| `src/agentic_claims/eval_worker/baselines/singlePrompt.py` | Baseline 1 |
| `src/agentic_claims/eval_worker/baselines/ruleBased.py` | Baseline 2 |
| `src/agentic_claims/eval_worker/analyses/selfConsistency.py` | 4.1 |
| `src/agentic_claims/eval_worker/analyses/crossModal.py` | 4.2 |
| `src/agentic_claims/eval_worker/analyses/verifierJudge.py` | 4.3 |
| `src/agentic_claims/eval_worker/analyses/disagreement.py` | 4.4 aggregate + failure digest |
| `src/agentic_claims/eval_worker/cost.py` | Cumulative cost + $10 circuit-breaker |
| `src/agentic_claims/eval_worker/pipelineContract.py` | `Pipeline` Protocol + `PipelineOutput` TypedDict |
| `templates/llmasjudge.html` | 4-tab page |
| `templates/partials/llmasjudge_overview.html` | Top summary + charts |
| `templates/partials/llmasjudge_runs.html` | Paginated run list |
| `templates/partials/llmasjudge_playground.html` | Ad-hoc scoring form |
| `templates/partials/llmasjudge_disagreement.html` | Heatmap + tables + failure digest |
| `static/js/llmasjudge.js` | Chart.js render + polling |
| `docs/eval-reflection.md` | Narrative reflection (rubric §5) |
| `alembic/versions/013_add_eval_runs_tables.py` | New schema |
| `src/agentic_claims/core/config.py` | 7 Spec-B knobs |
| `src/agentic_claims/web/main.py` | Register middleware + lifespan for worker |

Existing reused:
- `eval/src/dataset.py` — 20 benchmarks, category weights, metric mapping.
- `eval/src/metrics/*.py` — GEval + HallucinationMetric configurations.
- `eval/src/capture/*.py` — browser subagent (agentic pipeline runner).
- `eval/src/scoring.py` — metric aggregation.

## 4. UI — `/llmasjudge`

**Page:** single HTML page with four tabs driven by Alpine.js; all data fetched via `fetch()` into Chart.js render calls.

### Tab 1 — Overview (default)
- Top summary card — last run datetime, agentic weighted total, `Δ` vs Baseline 1 and Baseline 2.
- **Weighted-category bar chart** — five categories × three pipelines.
- **Per-benchmark bar chart** — 20 bars × three pipelines stacked.
- **"Run full eval" button** — POST `/llmasjudge/run`; rate-limited; disabled while a run is in progress.
- **Reflection block** — rendered from `docs/eval-reflection.md` (server-side markdown → HTML) — "when agentic wins / limitations / what disagreement surfaces."

### Tab 2 — Runs
- Paginated table (10/page) from `eval_runs` ordered by `started_at DESC`.
- Columns: when, git_sha (short), judge_model, agentic%, B1%, B2%, total delta, status.
- Click → expand inline to show detail: per-benchmark verdicts for all 3 pipelines, judge reasoning digest, cost, self-consistency variance, cross-modal diff.
- Filter controls: status = {all, finished, failed, interrupted}; pipeline delta threshold.

### Tab 3 — Playground
- Form fields:
  - Receipt input (upload image OR paste text — mutually exclusive).
  - Agent verdict dropdown (whitelisted: `pass | fail | requiresReview | requiresManagerApproval | requiresDirectorApproval`).
  - Justification text (≤500 chars).
  - Benchmark ID select (ER-001 … ER-020 or "custom").
  - [Score it] button.
- Submit → `POST /llmasjudge/playground` → server returns an HTML partial with score, reasoning, judge-model, latency, cost. HTMX swap (no full page reload).
- **Not persisted** — ephemeral.

### Tab 4 — Disagreement
- Fetch `/llmasjudge/analyses/latest` once; render four visualizations:
  1. **Self-consistency heatmap** — 20 benchmarks × 3 pipelines; cell color = consistency score; tooltip lists the 3 verdicts.
  2. **Cross-modal agreement table** — benchmarkId · verdict(image+text) · verdict(text-only) · agree? · deltaReason.
  3. **Primary vs verifier judge table** — benchmarkId · primaryScore · verifierScore · delta · disagree?
  4. **Failure-case digest** — top 5 by `disagreementScore`; each expands to show all three pipeline verdicts + LLM-generated failure hypothesis (<100 words).
- Every chart has a caption referencing the rubric dimension it addresses.

### Assets
- **Chart.js** via CDN; **chartjs-chart-matrix** plugin for the heatmap.
- No build tool; Alpine + HTMX stay consistent with the rest of the app.

## 5. Baselines (both executable end-to-end)

### 5.1 Baseline 1 — single-prompt single-model (`baselines/singlePrompt.py`)
- Single VLM call extracts receipt text (same VLM model as agentic).
- Single LLM call with the full policy text (~4–8K tokens) + receipt + justification; asks for structured JSON verdict.
- No RAG, no tools, no graph, no abuse guard, no critique.
- Implements `Pipeline` Protocol; outputs same `PipelineOutput` shape.

### 5.2 Baseline 2 — rule-based deterministic (`baselines/ruleBased.py`)
- Tesseract OCR for field extraction (pytesseract on ARM Linux — Tesseract package installed via apt in Dockerfile).
- Regex field extraction: merchant, total, date, currency.
- Keyword lookup table for category.
- Hardcoded threshold checks against per-category caps (duplicates of `core/config.py` constants, intentionally — the rule-based pipeline is a separate artifact).
- Zero LLM calls. Fully offline.
- Same output shape.

### 5.3 Shared contract (`pipelineContract.py`)

```python
from typing import Protocol, TypedDict

class PipelineOutput(TypedDict):
    verdict: str              # pass | fail | requiresReview | requiresManagerApproval | requiresDirectorApproval
    extractedFields: dict
    violations: list[dict]
    reasoning: str
    latencyMs: int
    llmCalls: int
    costUsd: float

class Pipeline(Protocol):
    name: str                 # "agentic" | "baseline_prompt" | "baseline_rules"
    async def runBenchmark(self, benchmark: dict) -> PipelineOutput: ...
```

The agentic pipeline in Spec B's worker invokes the LangGraph **directly in-process** (`buildGraph()` + `compile()` + `ainvoke()`), not via the browser/subagent flow in `eval/src/capture/runner.py`. The existing capture path uses Playwright + Claude subagents to drive the deployed UI; that depends on chromium + the Anthropic SDK, neither of which should live inside the production FastAPI container. Direct graph invocation is:

- deterministic (no browser flakiness in the rubric eval),
- cheaper (no subagent overhead),
- container-safe (no new heavyweight deps),
- still exercises the full agentic pipeline (intake → abuseGuard → compliance → fraud → advisor).

The existing `eval/run_eval.py` browser capture remains unchanged for its own CLI use case; Spec B's worker is a second, in-process entry point that shares the dataset + metrics but not the runner.

## 6. Rubric-required analyses

### 6.1 Self-consistency (`analyses/selfConsistency.py`)
- For each (pipelineId, benchmarkId): run `EVAL_SELF_CONSISTENCY_RUNS` (default 3) times at `temperature=0.3`.
- `consistencyScore = 1 - (H_observed / H_max)` where `H_observed` is the Shannon entropy of the 3 observed verdicts and `H_max = log2(3)` is the entropy ceiling.
- B2 is deterministic → `consistencyScore = 1.0` always; included as oracle baseline.
- `unstable = consistencyScore < 0.67` (i.e., all 3 runs must agree for a pass).

### 6.2 Cross-modal agreement (`analyses/crossModal.py`)
- Agentic pipeline only — baselines are single-modality.
- Each benchmark runs twice under agentic: image+text (normal) vs text-only (skip VLM, use `benchmark["textOnlyDescription"]`).
- `crossModalAgree = verdict_image_text == verdict_text_only`.
- Requires new field `textOnlyDescription` on every benchmark — authored once from PDF ground truth as a code change to `eval/src/dataset.py` (no DB migration; this is Python-level benchmark data).

### 6.3 Verifier judge (`analyses/verifierJudge.py`)
- Primary judge = `EVAL_JUDGE_MODEL` (defaults to `openrouter_model_llm`).
- Verifier judge = `EVAL_VERIFIER_MODEL` (defaults to `anthropic/claude-haiku-4-5` via OpenRouter).
- Both score each agentic benchmark output via DeepEval GEval, returning `[0,1]`.
- `verifierDisagree = abs(primaryScore - verifierScore) > EVAL_DISAGREEMENT_THRESHOLD` (default 0.25).

### 6.4 Aggregate disagreement (`analyses/disagreement.py`)
- `disagreementScore = 0.4 * (1 - consistencyScore) + 0.3 * (1 - crossModalAgree_numeric) + 0.3 * verifier_delta_normalized`, range `[0,1]`.
- Failure-case digest: top 5 by `disagreementScore`; each gets one verifier-judge call (temp 0) asking for a <100-word failure-mode hypothesis.

## 7. Storage (Approach C — hybrid)

### 7.1 `eval_runs` (new table)

```
id              bigserial pk
started_at      timestamptz not null default now()
finished_at     timestamptz null
status          text not null        -- queued | running | finished | failed | interrupted
git_sha         text not null
judge_model     text not null
verifier_model  text not null
config_json     jsonb not null
results_path    text not null        -- eval/results/{iso}.json
summary_json    jsonb null           -- {agenticPct, b1Pct, b2Pct, weightedTotal, deltas}
triggered_by    text not null        -- ip + session hash
```

### 7.2 `eval_judgments` (new table)

```
id                      bigserial pk
run_id                  bigint not null references eval_runs(id) on delete cascade
benchmark_id            text not null
pipeline                text not null          -- agentic | baseline_prompt | baseline_rules
self_consistency_runs   jsonb not null         -- [{verdict, score, latencyMs}, ...]
consistency_score       float not null
cross_modal_verdict     text null              -- agentic only
cross_modal_agree       boolean null
primary_judge_score     float not null
verifier_judge_score    float not null
verifier_agree          boolean not null
disagreement_score      float not null
cost_usd                float not null
reasoning_digest        text null              -- ≤500 chars
```

Indexes: `(run_id)`, `(benchmark_id)`, `(pipeline)`, `(disagreement_score DESC)`.

### 7.3 File of record
`eval/results/{started_at_iso}.json` — full DeepEval payload; unchanged from existing harness.

### 7.4 Migration (`alembic/versions/013_add_eval_runs_tables.py`)
Additive. Down-migration drops both tables — safe because no external FK references them.

## 8. Background worker + concurrency

### 8.1 Lifecycle
- Worker task created in `web/main.py` lifespan alongside the graph/checkpointer.
- Cancelled cleanly on app shutdown.
- One asyncio queue, `maxsize=1` (i.e., at most one queued run in addition to the running one).

### 8.2 Enqueue semantics
- `POST /llmasjudge/run`:
  - If the queue is full → `409 Conflict` ("an evaluation is already queued or running").
  - Otherwise: insert `eval_runs` row with `status=queued`; put `runId` on the queue; return `{runId, status: "queued"}`.
- Rate limit: 1 successful POST per hour per IP.

### 8.3 Worker loop
Each job runs `runner._executeRun(runId)`:
1. Set `status=running`, `started_at=now()`.
2. For each pipeline × benchmark × self-consistency iteration → run pipeline, insert/update the row's `self_consistency_runs` jsonb.
3. Cross-modal iteration (agentic × 20 text-only).
4. Verifier-judge scoring (20).
5. Aggregate disagreements.
6. Flush full JSON to `eval/results/{iso}.json`.
7. Update `summary_json`, `finished_at`, `status=finished`.
On exception: `status=failed`, `error` recorded in summary_json.

### 8.4 Progress
Worker updates `summary_json.progress = {completed, total, currentBenchmark, currentPipeline, iteration}` after every benchmark-iteration.
UI polls `GET /llmasjudge/runs/{id}/status` every 3 s while `status=running`.

### 8.5 Crash recovery
At app startup (lifespan init), run one SQL UPDATE setting any row with `status in ('running', 'queued')` to `'interrupted'`. Does not auto-resume. User re-kicks via the UI.

### 8.6 Memory / OOM safety
- Stream-append per benchmark to the JSON file; do not accumulate the full payload in memory.
- Truncate captured browser buffers after scoring.
- Hard cap: `EVAL_MAX_RESULT_JSON_MB = 10`.

## 9. Security + rate limiting

### 9.1 PublicRateLimitMiddleware (`publicRateLimit.py`)
Scoped to `/llmasjudge/*` only (sibling middleware to `RequestGuardMiddleware`).

| Path pattern | Limit | Window |
|---|---|---|
| `GET /llmasjudge*` | 60 req | 60 s |
| `POST /llmasjudge/playground` | 5 req | 60 s |
| `POST /llmasjudge/run` | 1 req | 3600 s |

On trip: `429 Too Many Requests` + plain text reason + audit row `action=public_ratelimit_trip actor=llmasjudge`.

### 9.2 Playground input validation
- Reuse `sanitizeUserText` (B3) on every text field.
- `receiptText ≤ 5000 chars`.
- `agentVerdict` server-side whitelist.
- `userJustification ≤ 500 chars` (reuse `max_justification_chars`).
- `benchmarkId` regex `^ER-\d{3}$|^custom$`.
- Image upload: `≤ 5 MB`, `{jpeg|png|webp}`, same OpenCV quality gate as runtime intake.

### 9.3 Config knobs (extend `core/config.py`)

```python
EVAL_JUDGE_MODEL: Optional[str] = None                     # None → openrouter_model_llm
EVAL_VERIFIER_MODEL: str = "anthropic/claude-haiku-4-5"    # via OpenRouter
EVAL_SELF_CONSISTENCY_RUNS: int = 3
EVAL_DISAGREEMENT_THRESHOLD: float = 0.25
EVAL_MAX_PLAYGROUND_CALLS_PER_MIN: int = 5
EVAL_MAX_RUNS_PER_HOUR: int = 1
EVAL_MAX_RESULT_JSON_MB: int = 10
EVAL_MAX_COST_USD_PER_RUN: float = 10.0
```

### 9.4 Cost circuit-breaker
Worker accumulates `cost_usd` across all `eval_judgments`; if it exceeds `EVAL_MAX_COST_USD_PER_RUN`, the run aborts with `status=failed`, `error=cost_cap_exceeded`. Partial data preserved. Audit row emitted.

### 9.5 Audit trail
Every rate-limit trip, cost-cap hit, and run-state transition writes to `audit_log` with `actor=llmasjudge`.

### 9.6 Explicitly NOT defended
- Distributed abuse across many IPs (Cloudflare is the follow-up if observed).
- Model leakage — LLM output is echoed verbatim; do not paste secrets.

## 10. Testing strategy

TDD, CamelCase, ≥90% coverage on new modules.

### 10.1 Unit tests (new)
- `test_baseline_single_prompt.py` — mocked VLM + LLM; output-shape + cost tracking.
- `test_baseline_rule_based.py` — 10+ regex/category fixtures; deterministic.
- `test_analysis_self_consistency.py` — entropy math against hand-tuned 3-run tuples.
- `test_analysis_cross_modal.py` — mocked agent; diff + audit row.
- `test_analysis_verifier_judge.py` — two mocked models; disagreement on known delta.
- `test_analysis_disagreement.py` — composite weighted score.
- `test_public_rate_limit_middleware.py` — FastAPI TestClient; 429.
- `test_llmasjudge_router.py` — all 8 endpoints; happy/throttle/cost-cap.
- `test_eval_worker_orchestrator.py` — happy-path, cancellation, crash recovery.
- `test_cost_circuit_breaker.py` — triggers at threshold, preserves partial data.

### 10.2 Integration tests (new)
- `test_eval_harness_end_to_end.py` — one benchmark × three pipelines, mocked LLMs; asserts DB rows + JSON file.
- `test_llmasjudge_page_render.py` — GET `/llmasjudge`, assert Alpine markup + tab targets.

### 10.3 Regression
- Every Spec A test stays green.
- `python eval/run_eval.py --benchmark ER-005 --skip-push` still works unchanged.

### 10.4 Merge gate
All tests green + one real benchmark run through the UI on a local `docker compose up` stack before deploying.

## 11. AWS deployment

Reuses the same `./mmga deploy` pattern:
1. Rsync `alembic/versions/013_*.py` to EC2.
2. `alembic upgrade head` inside the container.
3. `./mmga deploy` (rsyncs src + templates + rebuild + restart).
4. Docker image rebuilds with `tesseract-ocr` apt package (see Dockerfile delta in plan).
5. Verify `/llmasjudge` renders via `curl -o /dev/null -w %{http_code} https://mmga.mdaie-sutd.fit/llmasjudge` → 200.
6. Trigger one small run via the UI; verify `eval_runs` row + `eval/results/*.json`.

## 12. Rubric mapping

| Rubric line | Where satisfied |
|---|---|
| Agent Architecture: diagram + roles | Section 3 diagram + existing Spec A diagram |
| Agent Architecture: model + tool justifications | `eval_runs.config_json` + UI detail view |
| Agent Architecture: usable demo UI | `/llmasjudge` 4-tab page (§4) |
| Multimodal: ≥2 modalities | Cross-modal analysis (6.2) |
| Multimodal: modality interaction | Cross-modal agreement table |
| Control & Failure: error/uncertainty detection | Verifier judge disagreement (6.3) |
| Control & Failure: retry / self-critique / fallback | Self-consistency re-runs (6.1) + Spec A B6 critique |
| Evaluation: task-specific success criteria | 20 benchmarks in `dataset.py` |
| Evaluation: ≥2 baselines | Baselines 1 & 2 (§5) |
| Evaluation: analysis of failure cases | Failure-case digest (6.4) |
| Evaluation: self-consistency / cross-modal / verifier / disagreement | 6.1 / 6.2 / 6.3 / 6.4 |
| Reflection: when agentic is beneficial | `docs/eval-reflection.md` on Overview tab |
| Reflection: limitations | Same doc |

## 13. Risks + open questions

| # | Risk / question | Mitigation |
|---|---|---|
| R1 | DeepEval v3.x API drift | Pin to installed version in `pyproject.toml`; commit the lock before starting. |
| R2 | Worker OOM on t3.medium full run | Streaming writes (§8.6); cost cap (§9.4); JSON size cap (§9.3). |
| R3 | Public playground → credit drain | Per-IP rate limits (§9.1) + cost cap; Cloudflare/login fallback documented. |
| R4 | Baseline 2 regex brittleness inflates agentic delta | Document this as the point of B2 in reflection block; rubric-honest. |
| R5 | Tesseract ARM wheel availability | Install `tesseract-ocr` apt package in Dockerfile; verify in merge-gate smoke. |
| R6 | Verifier model 402 / quota | `EVAL_VERIFIER_MODEL` configurable + fallback to `OPENROUTER_FALLBACK_MODEL_LLM`. |
| R7 | `textOnlyDescription` missing from benchmarks | Author once in the migration PR; included in Task plan. |
| R8 | Rate-limit false positives on grader demo | 60 req/min browse is generous; documented to graders. |

## 14. Transition

Next step: invoke `superpowers:writing-plans` to produce the task-by-task implementation plan.
