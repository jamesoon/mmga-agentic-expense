"""Ensure W2 justification rules are present in the compliance system prompt."""

from agentic_claims.agents.compliance.prompts.complianceSystemPrompt import COMPLIANCE_SYSTEM_PROMPT


def testPromptContainsW2Header() -> None:
    assert "W2 Justification Rules" in COMPLIANCE_SYSTEM_PROMPT


def testPromptDiscussesUserInputFence() -> None:
    assert "<user_input>" in COMPLIANCE_SYSTEM_PROMPT


def testPromptForbidsHardOverride() -> None:
    # The prompt must explicitly forbid overriding hard violations via justification
    assert "hard" in COMPLIANCE_SYSTEM_PROMPT
    assert "MUST NOT be overridden" in COMPLIANCE_SYSTEM_PROMPT or "must not be overridden" in COMPLIANCE_SYSTEM_PROMPT.lower()


def testPromptDiscussesSoftPlus() -> None:
    assert "soft-plus" in COMPLIANCE_SYSTEM_PROMPT


def testPromptReactsToAbuseFlags() -> None:
    assert "abuseFlags" in COMPLIANCE_SYSTEM_PROMPT
