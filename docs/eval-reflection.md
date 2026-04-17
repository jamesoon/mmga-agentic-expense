# Evaluation Reflection (Rubric §5)

This document accompanies the `/llmasjudge` evaluation harness and provides the reflective commentary the project rubric §5 asks for. It is rendered into the Overview tab of the page as narrative context alongside the quantitative charts.

## Why agentic?

The agentic pipeline (`intake_gpt → abuseGuard → compliance → fraud → advisor`) does three things none of the baselines can:

1. **Citation-grounded verdicts.** When the agent flags a violation, it cites the specific policy clause retrieved from the RAG index. Baseline 1 (single-prompt) sometimes references the right clause but doesn't quote it verbatim; Baseline 2 (rule-based) has no concept of citation at all. This matters for SROIE-adjacent reasoning tasks (non-standard receipts, invoice routing) and for all RAGAS policy-question items.

2. **Escalation on uncertainty.** Low-quality images, ambiguous totals, and cross-receipt duplicates are surfaced as `requiresReview` with an explanation. B1 is confident-even-when-wrong; B2 silently computes whatever the regex returns.

3. **Modality interplay.** The cross-modal analysis (image+text vs text-only) shows the VLM carries real signal for the blurry-receipt and hand-written-receipt benchmarks — image-only inputs produce different verdicts than text-only ones, and the agent reconciles both before deciding.

## Where the baselines win or tie

1. **Trivial extraction.** For clean, typed, printed receipts with standard fields (company / date / total), all three pipelines agree. Baseline 2 is the cheapest at zero LLM calls and roughly equivalent accuracy on the clean subset. Baseline 1 is faster than agentic and comparable on simple cases.

2. **Deterministic policy caps.** Pure threshold questions ("is the amount over SGD 5000?") are trivially decidable by B2's arithmetic check. Agentic's B5 hard-cap branch lands at the same verdict but consumes an LLM-call's worth of latency/cost.

3. **Hallucination-free outputs.** B2 literally cannot hallucinate — no LLM, no generative output. When the rules match the test case, B2 is the safest option.

## What the disagreement analysis surfaces

- **Self-consistency variance** concentrates on soft-violation benchmarks where the justification-aware compliance flip can go either way under stochasticity. Re-running each (pipeline, benchmark) three times at temperature 0.3 exposes this.
- **Cross-modal disagreement** concentrates on SROIE items with low-quality receipts or non-standard layouts (ER-019/020 class). Text-only and image+text runs diverge there — the visual signal is load-bearing.
- **Verifier-judge disagreement** concentrates on ambiguous multi-step reasoning items where primary (Qwen family) and verifier (Claude Haiku family) weight the policy clauses differently. These are the items most worth human review.
- **Aggregate `disagreementScore`** surfaces the top-5 failure cases to the UI's failure-digest block. This is the direct rubric deliverable for "analysis of failure cases."

## Limitations

1. **LLM-as-Judge blind spots.** Both the primary and verifier judge are LLMs. When they share a blind spot (e.g., both miss a subtle policy nuance), neither the verdict nor the disagreement score will flag the issue. The two-judge-family setup mitigates this but does not eliminate it. Ground-truth labels from SROIE and RAGAS hand-authored questions backstop this.

2. **Baseline 2 is deliberately brittle.** The regex/keyword rule-based pipeline is engineered as a minimum-viable non-agentic reference — a serious production rule-based system would use a far more carefully tuned lexicon, better OCR preprocessing, and language-specific rules. Treat the "agentic wins by 40%" headline as "agentic wins vs a thrown-together baseline", not "agentic wins vs every possible non-agentic system."

3. **Dataset scale is small.** 20 SROIE items + 15 RAGAS questions = 35 test cases. Enough for rubric defence, not enough for statistically sound generalisation claims. Every conclusion here is an *indication*, not a proof.

4. **Playground scorings are ephemeral.** Ad-hoc scores from the Playground tab are not persisted — they do not accumulate evidence for or against any pipeline over time.

5. **Cost circuit-breaker may truncate runs.** `EVAL_MAX_COST_USD_PER_RUN=10.0` protects against runaway spend; a full run that exceeds it is marked `failed` with partial data preserved. Edge cases where cost tracking under-counts actual OpenRouter spend are possible.

6. **In-process worker has no horizontal scale.** The `asyncio.Queue(maxsize=1)` guarantees at most one run at a time — intentional for scope, but a single misbehaving pipeline can block the queue until it times out or is cancelled.

## When would we *not* go agentic?

- Real-time latency budgets (< 1 s end-to-end). Agentic's multi-step graph and LLM tool calls make that infeasible.
- High-throughput batch with cheap inputs. If you're classifying 1M clean typed receipts into four buckets, a regex + keyword system (B2-grade) is 1000× cheaper and sufficient.
- Environments with strict determinism requirements (regulated finance reproducibility). Agentic's self-consistency variance, while small, is non-zero; a deterministic pipeline may be mandated.

## Rubric cross-reference

| Rubric line | Evidence on this page |
|---|---|
| Task-specific success criteria | SROIE gold F1 + RAGAS metric thresholds (Layer A / Layer B) |
| Comparison against ≥ 2 baselines | Per-benchmark chart on Overview tab shows agentic vs B1 vs B2 |
| Self-consistency checks | Disagreement tab — consistency score per (pipeline, benchmark) |
| Cross-modal agreement checks | Disagreement tab — image+text vs text-only verdicts for agentic |
| Verifier models | Disagreement tab — primary judge vs verifier judge scores |
| Disagreement analysis | Disagreement tab — top-5 failure-case digest |
| When agentic is beneficial | This document, §1 above |
| Limitations | This document, §4 above |
