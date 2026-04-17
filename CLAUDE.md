# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

Multi-agent multimodal system that automates SUTD expense claim processing via a LangGraph pipeline. Claimants upload receipt images in a FastAPI + server-rendered web UI; LangGraph agents handle extraction, abuse-guarding, compliance, fraud detection, and final routing. Target: <3 min per claim vs. 15-25 min manually.

**Current phase**: Phase 14 — intake-gpt ReAct replacement (custom subgraph) + post-merge hardening (justification-aware compliance, 8-layer abuse defense). See `.planning/ROADMAP.md` and `docs/superpowers/specs/` for the active design.

## Active design (post-mmae-merge)

The running design is captured in `docs/superpowers/specs/` (latest dated spec). Highlights:

- **Baseline adoption:** overwrite with `../mmae/` baseline (Phase 14 intake-gpt), then re-apply all preserved ops/admin features on top.
- **Preserved features:** health dashboard, logs viewer, policies UI, admin/reviewer surfaces (analytics, audit, dashboard, manage, review, pages), AWS deploy scripts (EC2 + RDS + Lambda), full LLM-based compliance/fraud/advisor agents, shared agent utilities (`agents/shared/`), session + RBAC auth, file-based log rotation.
- **New functional changes:** user-typed justification is a first-class signal to compliance (soft-fail flips to manager-approval; hard caps are unconditional); an 8-layer abuse defense spans web middleware, intake tools, a new `abuseGuard` graph node, compliance internals, and audit logging.
- **Rubric alignment:** diagram + role table (Agent Architecture), image + text + policy RAG (Multimodal Grounding), B3 injection firewall + B6 self-critique + 402 LLM fallback (Control & Failure Handling), audit trail seeded here for Spec B eval harness (Evaluation), "when agentic / limitations" discussion (Reflection).

## Commands

```bash
# Start all 7 services (app, postgres, qdrant, 4 MCP servers)
docker compose up -d --build

# Run all tests (from host, not inside Docker)
poetry run pytest tests/ -v

# Run a single test file
poetry run pytest tests/test_intake_agent.py -v

# Run a single test by name
poetry run pytest tests/test_intake_agent.py::test_intake_node_returns_ai_message -v

# Lint / format
poetry run ruff check src/ tests/
poetry run ruff format src/ tests/

# Run DB migrations (inside Docker)
docker compose exec app poetry run alembic upgrade head

# Ingest policy docs into Qdrant (run from host, needs Qdrant on localhost:6333)
python scripts/ingest_policies.py

# Create a new Alembic migration after model changes
poetry run alembic revision --autogenerate -m "description"
```

## Architecture

```
┌─ FastAPI web layer ───────────────────────────────────────────────┐
│ Middleware: SessionAuth │ RateLimit+LenCaps (B1) │ UserQuotas (B8)│
│ Routers: chat, auth, dashboard, health, logs, policies,           │
│          analytics, audit, manage, review, pages                  │
└───────────────────────────────────────────────────────────────────┘
                          ↓ sanitized request
┌─ LangGraph agent graph ───────────────────────────────────────────┐
│                                                                   │
│  intake_gpt ──▶ abuseGuard (NEW) ──▶ evaluatorGate                │
│                     │                    │                        │
│                     ▼                    ▼ claimSubmitted         │
│                abuseFlags           postSubmission                │
│                                     ├──────────┐                  │
│                                     ▼          ▼                  │
│                                 compliance   fraud   (parallel)   │
│                                     │          │                  │
│                                     └────┬─────┘                  │
│                                          ▼                        │
│                                     advisor ──▶ END               │
│                                                                   │
│  intake_gpt tools: extractReceiptFields, searchPolicies,          │
│    convertCurrency, submitClaim, getClaimSchema,                  │
│    requestHumanInput ────▶ InjectionFirewall (B3)                 │
│                                                                   │
│  AsyncPostgresSaver (checkpointer, persists ClaimState per node)  │
└───────────────────────────────────────────────────────────────────┘
```

**ClaimState** (`core/state.py`) flows through the graph. Core fields: `claimId`, `status`, `messages` (append-only via `add_messages`), `extractedReceipt`, `violations`, `currencyConversion`, `claimSubmitted`, `intakeFindings`, `complianceFindings`, `fraudFindings`, `dbClaimId`.

Post-merge additions:
- `userJustification: str | None` — user-typed purpose/explanation, always collected
- `abuseFlags: dict | None` — `{coherenceOk, crossCheckOk, injectionSanitized, reasons: [...]}` produced by `abuseGuard`
- `critiqueResult: dict | None` — compliance self-critique verdict (B6)
- `userQuotaSnapshot: dict | None` — per-request quota state for audit

**intake_gpt** (`agents/intake_gpt/graph.py`) is a custom LangGraph subgraph (Phase 14, replaces the prebuilt ReAct loop). It carries 6 tools:
- `extractReceiptFields` — OpenCV quality gate, then direct VLM call (image never enters LLM context)
- `searchPolicies` — calls mcp-rag (Qdrant semantic search)
- `convertCurrency` — calls mcp-currency (Frankfurter API)
- `submitClaim` — calls mcp-db (PostgreSQL)
- `getClaimSchema` — schema-driven field collection
- `requestHumanInput` — LangGraph `interrupt()` for field confirmation + justification capture

**abuseGuard** (`agents/abuse_guard/node.py`, NEW) runs between intake_gpt and evaluatorGate. Deterministic coherence gate (B2) + LLM cross-check of receipt ↔ justification (B4). Writes `abuseFlags` to state; downstream compliance respects these flags.

**Compliance** (`agents/compliance/node.py`) is the justification-aware evaluator:
- Reads `userJustification` + `abuseFlags` alongside `extractedReceipt` and `violations`.
- Weight = W2: justification can upgrade a *soft* violation to "requires manager approval"; hard monetary caps (B5) are unconditional.
- Self-critique step (B6) — second LLM call, different prompt + lower temperature, flips verdict to `requiresReview` on disagreement.
- Writes `audit_log` entries for every guard trip (B7) with `actor=abuse_guard` or `actor=compliance_agent`.

**Image flow**: Receipt images are stored in `core/imageStore.py` (keyed by `claimId`). The LLM only sees a text message; `extractReceiptFields` retrieves the image from the store by `claimId`. This avoids ~58K tokens of base64 in the LLM context.

**MCP servers** (4 Docker containers, Streamable HTTP transport on `/mcp`):
- `mcp-rag` (port 8001) — policy search via Qdrant + SentenceTransformers
- `mcp-db` (port 8002) — claims CRUD (PostgreSQL)
- `mcp-currency` (port 8003) — Frankfurter API currency conversion
- `mcp-email` (port 8004) — SMTP notifications (stubs locally via Mailhog)

Health check: `curl` against `/mcp` returns `406` when healthy (Streamable HTTP requires MCP client headers).

## Preserved Features (post-merge layer)

The `../mmae/` baseline ships Phase 14 intake-gpt but lacks the ops and admin surfaces built here. These are re-applied after baseline adoption:

| Feature group | Location | Purpose |
|---------------|----------|---------|
| Health dashboard | `web/routers/health.py` + `templates/health.html` | DB / Qdrant / OpenRouter / Frankfurter / 4 MCP servers / LangGraph / session / system-metric checks; `/health/json` for monitoring |
| Logs viewer | `web/routers/logs.py` + `templates/logs.html` | Per-service Docker Engine API log view with error/warning summaries; `/logs/json` |
| Policies UI | `web/routers/policies.py` + `policy/system/` | Policy admin surface |
| Admin / reviewer | `web/routers/{analytics,audit,dashboard,manage,review,pages}.py` + templates | Internal ops surfaces |
| AWS deployment | `scripts/aws/*` + `docker-compose.prod.yml` + `.env.prod.example` | EC2 (free tier) + RDS + Lambda Function URLs for MCP |
| Real agents | `agents/{compliance,fraud,advisor}/` + `agents/shared/` | Full LLM-based evaluators (not the stubs from the baseline) |
| Session + RBAC | `web/auth.py` + users-table Alembic migration | Role-gated routes (reviewer, manager, director, admin) |
| File log rotation | `logs/app-YYYYMMDD-*.log` | Structured JSON logs rolled by time |

## Abuse Boundaries (8 layers)

All 8 layers are wired end-to-end; each boundary trip writes an `audit_log` entry with `actor=abuse_guard` (or `actor=compliance_agent` for B5/B6):

1. **Length + rate caps** (web middleware) — justification ≤500 chars, message ≤2000 chars, reject control/binary chars, N msgs/min per session.
2. **Justification coherence gate** (`abuseGuard` node) — min length, non-stopword tokens, category-keyword OR recognised-reason match; failure downgrades justification signal to "absent."
3. **Prompt-injection firewall** (intake tools + chat router) — neutralises known injection patterns; user text enters LLM prompts only as quoted *data* inside a fixed template.
4. **Receipt ↔ justification cross-check** (`abuseGuard` node) — a cheap LLM call flags contradictions between receipt category/merchant/amount and the user's stated reason → `requiresReview`.
5. **Hard monetary ceilings** (compliance, deterministic) — per-receipt / per-claim / per-employee-per-month caps; above ceiling auto-escalates to director regardless of justification.
6. **Self-critique verifier** (compliance internal) — second LLM call with different prompt + lower temperature reads the verdict; disagreement flips verdict to `requiresReview`.
7. **Audit trail** (ubiquitous) — every sanitization, cap hit, or critic flip written to `audit_log`.
8. **User quotas** (web middleware) — per-user-per-day claim-submission cap; per-user-per-hour retry cap after a fail verdict.

## Key Conventions

- **Naming**: CamelCase everywhere — functions, variables, classes, test functions.
- **Agent nodes**: Must be `async def`. Return only the keys being changed (partial state update). Never import config or database infrastructure directly in agent nodes.
- **MCP client** (`agents/intake/utils/mcpClient.py`): All MCP tool calls go through this HTTP client, not the MCP SDK.
- **Config**: All values from `.env.local` (dev) or `tests/.env.test` (tests) via pydantic-settings (`core/config.py`). `getSettings()` is the entry point.
- **LLM vs VLM**: `OPENROUTER_MODEL_LLM` for agent reasoning (text), `OPENROUTER_MODEL_VLM` for receipt extraction (vision). Both configured in `.env.local`.
- **Abuse boundaries**: user-typed text is *data*, never instructions. It enters LLM prompts only via fixed templates after injection-firewall sanitization. Justification is a signal, not an override — hard caps and the self-critique verifier are unconditional.
- **Justification handling**: compliance treats user justification as W2 — it can upgrade a *soft* violation (mild over-cap, missing preferred vendor) to "requires manager approval" but cannot override a *hard* cap (B5).

## Planning Artifacts

| What | Where |
|------|-------|
| Active design spec (Spec A) | `docs/superpowers/specs/YYYY-MM-DD-mmae-merge-and-hardening-design.md` |
| Next brainstorm (Spec B) | Evaluation harness: LLM-as-Judge + 2 baselines + self-consistency / cross-modal / verifier-disagreement analysis |
| Phase roadmap + status | `.planning/ROADMAP.md` |
| Active phase state | `.planning/STATE.md` |
| Per-phase execution plans | `.planning/phases/{phase}/` (includes `14-intake-gpt-react-replacement/`) |
| Full requirements (49) | `.planning/REQUIREMENTS.md` |
| Project notes / decisions | `docs/project_notes/` |
| Merge manifest (what moved where) | `MERGE_MANIFEST.md` (produced during Step 2.2 of Spec A) |

## Rubric Mapping

| Rubric section | Where it lives in this codebase |
|----------------|---------------------------------|
| Agent Architecture: diagram + roles | Architecture diagram above; agent role table in the active spec |
| Agent Architecture: model + tool justifications | `.planning/research/STACK.md`; model choice in `core/config.py`; tool list in `agents/intake_gpt/graph.py` |
| Agent Architecture: usable UI | `templates/` + `web/routers/` (FastAPI + server-rendered HTML) |
| Multimodal Grounding: ≥2 modalities | Image (VLM extraction) + text (user justification) + text (policy RAG) |
| Multimodal Grounding: modality interaction | `abuseGuard` receipt ↔ justification cross-check (B4) |
| Control & Failure: error/uncertainty detection | B2 coherence gate; compliance parse-failure fallback; OpenRouter 402 fallback in `agents/shared/llmFactory.py` |
| Control & Failure: retry / self-critique / fallback | B6 self-critique verifier; LLM fallback model chain |
| Evaluation | Seeded by audit trail + abuse-flag structured fields; deep harness is **Spec B (separate brainstorm)** |
| Reflection | "When agentic is beneficial / limitations" discussion added to README post-merge |
