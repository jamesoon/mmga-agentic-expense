"""Cross-modal agreement analysis (Spec B §6.2). Agentic pipeline only.

Short-circuits when the benchmark has no image file (e.g. RAGAS text-only
policy questions). In that case every field is None and `agree` is None.
"""

from __future__ import annotations

from agentic_claims.eval_worker.baselines.agentic import AgenticPipeline


async def compareCrossModal(benchmark: dict) -> dict:
    hasImage = bool(benchmark.get("file"))
    if not hasImage:
        return {
            "benchmarkId": benchmark.get("benchmarkId"),
            "verdictImageText": None,
            "verdictTextOnly": None,
            "agree": None,
            "deltaReason": "no image — cross-modal N/A",
        }
    imgResult = await AgenticPipeline(textOnly=False).runBenchmark(benchmark)
    textResult = await AgenticPipeline(textOnly=True).runBenchmark(benchmark)
    agree = imgResult["verdict"] == textResult["verdict"]
    return {
        "benchmarkId": benchmark.get("benchmarkId"),
        "verdictImageText": imgResult["verdict"],
        "verdictTextOnly": textResult["verdict"],
        "agree": agree,
        "deltaReason": "" if agree else
                       f"image → {imgResult['verdict']}, text-only → {textResult['verdict']}",
    }
