"""Self-critique verifier runner (Spec A B6)."""

from __future__ import annotations

import json
import logging
from typing import Any

from langchain_core.messages import HumanMessage, SystemMessage

from agentic_claims.agents.compliance.prompts.critiqueSystemPrompt import CRITIQUE_SYSTEM_PROMPT
from agentic_claims.agents.shared.llmFactory import buildAgentLlm
from agentic_claims.agents.shared.utils import extractJsonBlock
from agentic_claims.core.config import getSettings

logger = logging.getLogger(__name__)


def _loadSettings():
    try:
        return getSettings()
    except Exception:
        return None


async def runSelfCritique(
    *,
    originalVerdict: str,
    context: dict,
    settingsOverride: Any | None = None,
) -> dict:
    """Run the second-pass critique LLM call.

    Returns a dict with keys:
      - critiqueAgrees: bool
      - critiqueVerdict: str
      - critiqueReasoning: str (<=300 chars)
      - originalVerdict: str
      - finalVerdict: str  (= originalVerdict if agrees, else critiqueVerdict or requiresReview)
      - rawLlmResponse: str
    """
    settings = settingsOverride or _loadSettings()

    if settings is not None and not settings.compliance_critique_enabled:
        return {
            "critiqueAgrees": True,
            "critiqueVerdict": originalVerdict,
            "critiqueReasoning": "Critique disabled in config.",
            "originalVerdict": originalVerdict,
            "finalVerdict": originalVerdict,
            "rawLlmResponse": "",
        }

    temperature = (
        getattr(settings, "compliance_critique_temperature", 0.0) if settings is not None else 0.0
    )
    try:
        llm = buildAgentLlm(settings, temperature=temperature, useFallback=True)
    except Exception as exc:
        logger.warning("runSelfCritique: buildAgentLlm failed — err=%s", exc)
        return {
            "critiqueAgrees": False,
            "critiqueVerdict": "requiresReview",
            "critiqueReasoning": f"Critique builder failed: {exc}",
            "originalVerdict": originalVerdict,
            "finalVerdict": "requiresReview",
            "rawLlmResponse": "",
        }

    user = (
        f"Original verdict: {originalVerdict}\n"
        f"Context JSON: {json.dumps(context, default=str)[:4000]}\n"
        "Decide whether to agree."
    )

    try:
        resp = await llm.ainvoke(
            [SystemMessage(content=CRITIQUE_SYSTEM_PROMPT), HumanMessage(content=user)]
        )
        raw = resp.content if hasattr(resp, "content") else str(resp)
    except Exception as exc:
        logger.warning("runSelfCritique: LLM failure — err=%s", exc)
        return {
            "critiqueAgrees": False,
            "critiqueVerdict": "requiresReview",
            "critiqueReasoning": f"Critique LLM failed: {exc}",
            "originalVerdict": originalVerdict,
            "finalVerdict": "requiresReview",
            "rawLlmResponse": "",
        }

    block = extractJsonBlock(raw) or raw
    try:
        parsed = json.loads(block)
    except (ValueError, TypeError):
        return {
            "critiqueAgrees": False,
            "critiqueVerdict": "requiresReview",
            "critiqueReasoning": "Malformed critique JSON.",
            "originalVerdict": originalVerdict,
            "finalVerdict": "requiresReview",
            "rawLlmResponse": raw,
        }

    agree = bool(parsed.get("agree", False))
    critiqueVerdict = str(parsed.get("verdict", originalVerdict))
    reasoning = str(parsed.get("reasoning", ""))[:300]
    finalVerdict = originalVerdict if agree else (critiqueVerdict or "requiresReview")
    return {
        "critiqueAgrees": agree,
        "critiqueVerdict": critiqueVerdict,
        "critiqueReasoning": reasoning,
        "originalVerdict": originalVerdict,
        "finalVerdict": finalVerdict,
        "rawLlmResponse": raw,
    }
