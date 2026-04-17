"""Spec A — userJustification field must exist in IntakeGptState (9.2)."""

from agentic_claims.agents.intake_gpt.state import IntakeGptState


def testIntakeGptStateHasUserJustificationField() -> None:
    assert "userJustification" in IntakeGptState.__annotations__
