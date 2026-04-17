"""Coherence gate tests (B2)."""

from agentic_claims.agents.abuse_guard.coherence import checkJustificationCoherence


def testEmptyStringFails() -> None:
    ok, reason = checkJustificationCoherence("")
    assert not ok and "empty" in reason.lower()


def testWhitespaceOnlyFails() -> None:
    ok, _ = checkJustificationCoherence("   ")
    assert not ok


def testTooShortFails() -> None:
    ok, _ = checkJustificationCoherence("ok")
    assert not ok


def testAllStopwordsFails() -> None:
    ok, _ = checkJustificationCoherence("the and of to a in is it for")
    assert not ok


def testGibberishFails() -> None:
    ok, _ = checkJustificationCoherence("asdfqwerzxcvmnbv")
    assert not ok


def testCategoryKeywordPasses() -> None:
    ok, _ = checkJustificationCoherence("Client meeting meals")
    assert ok


def testRecognisedReasonPasses() -> None:
    ok, _ = checkJustificationCoherence("I was at a client meeting with Acme Corp and had dinner.")
    assert ok


def testTravelKeywordPasses() -> None:
    ok, _ = checkJustificationCoherence("overnight travel to Kuala Lumpur for workshop")
    assert ok


def testTrainingKeywordPasses() -> None:
    ok, _ = checkJustificationCoherence("attended training course fees paid")
    assert ok


def testEmergencyKeywordPasses() -> None:
    ok, _ = checkJustificationCoherence("medical emergency at airport needed taxi fare")
    assert ok


def testNoKeywordFailsEvenIfCoherent() -> None:
    ok, _ = checkJustificationCoherence("I bought this yesterday for myself")
    assert not ok


def testLongerTextWithKeywordPasses() -> None:
    ok, _ = checkJustificationCoherence(
        "this expense covers a team dinner with three external clients discussing a proposal"
    )
    assert ok
