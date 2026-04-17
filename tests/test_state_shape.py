"""Assert ClaimState carries Spec-A fields so TypedDict serialization/checkpointer is compatible."""

from agentic_claims.core.state import ClaimState


def testClaimStateHasUserJustificationField() -> None:
    assert "userJustification" in ClaimState.__annotations__


def testClaimStateHasAbuseFlagsField() -> None:
    assert "abuseFlags" in ClaimState.__annotations__


def testClaimStateHasCritiqueResultField() -> None:
    assert "critiqueResult" in ClaimState.__annotations__


def testClaimStateHasUserQuotaSnapshotField() -> None:
    assert "userQuotaSnapshot" in ClaimState.__annotations__
