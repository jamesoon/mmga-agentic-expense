"""Eval suite configuration -- loads judge model and credentials from environment.

Decoupled from the app (no imports from agentic_claims).
"""

import os
from dataclasses import dataclass, field
from pathlib import Path

from deepeval.models import LiteLLMModel

_EVAL_DIR = Path(__file__).resolve().parent.parent


@dataclass
class EvalConfig:
    judgeModel: LiteLLMModel
    appUrl: str
    dbUrl: str
    resultsDir: Path
    invoicesDir: Path
    evalUsername: str
    evalPassword: str
    anthropicApiKey: str


def getEvalConfig() -> EvalConfig:
    """Read environment variables, validate required keys, return EvalConfig.

    Required env vars:
      OPENROUTER_API_KEY   -- judge LLM authentication
      ANTHROPIC_API_KEY    -- Claude subagent invocation

    Optional env vars (have defaults):
      EVAL_APP_URL         -- default https://mmga.mdaie-sutd.fit (AWS deployment)
      DATABASE_URL         -- default RDS endpoint
      EVAL_USERNAME        -- default james (reviewer role)
      EVAL_PASSWORD        -- default james123
    """
    openrouterApiKey = os.environ.get("OPENROUTER_API_KEY", "")
    if not openrouterApiKey:
        raise ValueError(
            "OPENROUTER_API_KEY environment variable is required for the judge model"
        )

    anthropicApiKey = os.environ.get("ANTHROPIC_API_KEY", "")
    if not anthropicApiKey:
        raise ValueError(
            "ANTHROPIC_API_KEY environment variable is required for Claude subagent invocation"
        )

    judgeModel = LiteLLMModel(
        model="openrouter/openai/gpt-4o",
        api_key=openrouterApiKey,
        base_url="https://openrouter.ai/api/v1",
    )

    appUrl = os.environ.get("EVAL_APP_URL", "https://mmga.mdaie-sutd.fit")
    dbUrl = os.environ.get(
        "DATABASE_URL",
        "postgresql://agentic:agentic_password@mmga-expense-postgres.cfg6qy4oqaqg.ap-southeast-1.rds.amazonaws.com:5432/agentic_claims",
    )
    evalUsername = os.environ.get("EVAL_USERNAME", "james")
    evalPassword = os.environ.get("EVAL_PASSWORD", "james123")

    return EvalConfig(
        judgeModel=judgeModel,
        appUrl=appUrl,
        dbUrl=dbUrl,
        resultsDir=_EVAL_DIR / "results",
        invoicesDir=_EVAL_DIR / "invoices",
        evalUsername=evalUsername,
        evalPassword=evalPassword,
        anthropicApiKey=anthropicApiKey,
    )
