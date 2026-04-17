"""Validate Spec-B config knobs exist with correct defaults."""

from pathlib import Path

from agentic_claims.core.config import Settings

# Load from the test env file (satisfies required fields) but verify that
# Spec B keys use their hardcoded defaults (not set in .env.test).
_ENV_TEST = Path(__file__).parent / ".env.test"


def testEvalSelfConsistencyRunsDefault() -> None:
    s = Settings(_env_file=str(_ENV_TEST))
    assert s.eval_self_consistency_runs == 3


def testEvalVerifierModelDefault() -> None:
    s = Settings(_env_file=str(_ENV_TEST))
    assert s.eval_verifier_model == "anthropic/claude-haiku-4-5"


def testEvalDisagreementThresholdDefault() -> None:
    s = Settings(_env_file=str(_ENV_TEST))
    assert s.eval_disagreement_threshold == 0.25


def testEvalMaxPlaygroundCallsPerMinDefault() -> None:
    s = Settings(_env_file=str(_ENV_TEST))
    assert s.eval_max_playground_calls_per_min == 5


def testEvalMaxRunsPerHourDefault() -> None:
    s = Settings(_env_file=str(_ENV_TEST))
    assert s.eval_max_runs_per_hour == 1


def testEvalMaxResultJsonMbDefault() -> None:
    s = Settings(_env_file=str(_ENV_TEST))
    assert s.eval_max_result_json_mb == 10


def testEvalMaxCostUsdPerRunDefault() -> None:
    s = Settings(_env_file=str(_ENV_TEST))
    assert s.eval_max_cost_usd_per_run == 10.0


def testEvalJudgeModelDefault() -> None:
    s = Settings(_env_file=str(_ENV_TEST))
    assert s.eval_judge_model is None
