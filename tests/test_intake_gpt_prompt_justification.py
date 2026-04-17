"""Verify intake_gpt prompt instructs justification collection (Spec A 9.1)."""

from agentic_claims.agents.intake_gpt.prompt import INTAKE_GPT_SYSTEM_PROMPT


def testPromptMentionsJustification() -> None:
    assert "justification" in INTAKE_GPT_SYSTEM_PROMPT.lower()


def testPromptMentionsUserInputFence() -> None:
    assert "<user_input>" in INTAKE_GPT_SYSTEM_PROMPT


def testPromptMentionsRequestHumanInput() -> None:
    assert "requestHumanInput" in INTAKE_GPT_SYSTEM_PROMPT


def testPromptMentionsPurposeOfExpense() -> None:
    assert (
        "Purpose of expense" in INTAKE_GPT_SYSTEM_PROMPT
        or "purpose of expense" in INTAKE_GPT_SYSTEM_PROMPT.lower()
    )
