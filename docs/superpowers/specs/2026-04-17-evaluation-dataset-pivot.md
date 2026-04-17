# Spec B Dataset Pivot — MMGA → SROIE + RAGAS

**Status:** Supersedes MMGA benchmark source in Spec B (`2026-04-17-evaluation-harness-llm-judge-design.md`).
**Date:** 2026-04-17
**Reason:** Rubric grading carries more weight with public, citation-grade sources. SROIE (ICDAR 2019) is the standard receipt-extraction benchmark; RAGAS is the de-facto RAG-evaluation metric framework. Replacing the homegrown MMGA PDF with both gives orthogonal, defensible coverage of *extraction* and *policy reasoning*.

## What changes

### Two test layers instead of one MMGA list

| Layer | Source | Count | Measures |
|---|---|---|---|
| **A — Extraction** | SROIE sample (ICDAR 2019) | 20 receipts | Per-field precision / recall / F1 on `company`, `address`, `date`, `total` against SROIE gold JSON |
| **B — Policy reasoning** | Hand-authored questions grounded in `src/agentic_claims/policy/*.md` | 15 questions | RAGAS `Faithfulness`, `ContextualPrecision`, `ContextualRecall`, `AnswerRelevancy` via DeepEval |

Total test cases: **35** (vs. 20 MMGA). Per-category weighting from rubric stays the same; Layer A ≈ extraction + classification, Layer B ≈ reasoning + safety.

### Dataset on disk

- `eval/sroie_samples/` — NEW. 20 `{name}.jpg` + `{name}.txt` (OCR) + `{name}.json` (gold labels) sourced from the SROIE ICDAR 2019 release. See `eval/sroie_samples/README.md` (Task 4.2b creates this) for provenance + license note.
- `eval/ragas_questions.py` — NEW. 15 question dicts, each with `{question, groundTruthClause, policyFile, expectedVerdict}`.

### Code changes vs. the original plan

| Original plan file / task | New behavior |
|---|---|
| `eval/src/dataset.py` — 20 MMGA benchmarks | **Remove** MMGA dataset (keep file as deprecation stub with a pointer to the new loaders). |
| Task 4.2 "author `textOnlyDescription` for every benchmark" | **Dropped.** SROIE ships with clean OCR text (`{name}.txt`); RAGAS questions are text-native. Cross-modal analysis becomes: for SROIE items — run agentic with image+text vs text-only-from-SROIE-OCR; for RAGAS items — N/A (skip cross-modal for Layer B, these are text-only by nature). |
| New: `eval/src/sroiLoader.py` | Loads 20 SROIE samples + gold labels. |
| New: `eval/src/ragasLoader.py` | Loads 15 RAGAS questions. |
| New: `eval/src/metrics/sroieF1.py` | Per-field F1 scorer for Layer A. |
| New: `eval/src/metrics/ragasMetrics.py` | Wraps DeepEval's RAGAS-equivalent metrics (`FaithfulnessMetric`, `ContextualPrecisionMetric`, `ContextualRecallMetric`, `AnswerRelevancyMetric`) for Layer B. |

### Rubric mapping (unchanged)

Every rubric line from Spec B §12 still lands on Layer A or Layer B:

| Rubric line | Now satisfied by |
|---|---|
| Task-specific success criteria | SROIE gold F1 + RAGAS metric thresholds |
| ≥ 2 baselines (B1 + B2) | Unchanged — baselines score both layers |
| Self-consistency | Unchanged — re-run 3× per (pipeline, item) |
| Cross-modal | SROIE only — image vs SROIE-provided OCR text |
| Verifier judges | RAGAS metrics already use two models under the hood; plus primary vs verifier for GEval on SROIE |
| Aggregate disagreement | Unchanged — weighted composite across both layers |

### What is NOT changing

- Three pipelines (agentic, baseline_prompt, baseline_rules) — same code, consume items from either loader.
- Worker architecture, queue, cost breaker, rate-limit middleware, storage schema — all unchanged.
- `/llmasjudge` page tabs — unchanged.
- Phase 1 (foundation) — already landed, still valid.

## SROIE license note

SROIE 2019 is research-only; re-distributed widely on GitHub and HuggingFace. We pull 20 samples into `eval/sroie_samples/` with attribution in the README. If a formal license is required, use `darentang/sroie` HuggingFace dataset card as the source of record.
