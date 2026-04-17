"""Spec B pipeline contract tests."""

from agentic_claims.eval_worker.pipelineContract import Pipeline, PipelineOutput


def testPipelineOutputRequiredKeys() -> None:
    assert set(PipelineOutput.__annotations__) == {
        "verdict", "extractedFields", "violations", "reasoning",
        "latencyMs", "llmCalls", "costUsd",
    }


def testPipelineProtocolHasRunBenchmark() -> None:
    assert hasattr(Pipeline, "runBenchmark")
