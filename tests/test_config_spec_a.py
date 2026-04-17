"""Validate Spec-A config knobs exist with correct defaults."""

import pytest

from agentic_claims.core.config import Settings


def testHardCapPerReceiptDefault(testSettings: Settings) -> None:
    assert testSettings.hard_cap_per_receipt_sgd == 5000.0


def testHardCapPerClaimDefault(testSettings: Settings) -> None:
    assert testSettings.hard_cap_per_claim_sgd == 10000.0


def testHardCapPerEmployeeMonthDefault(testSettings: Settings) -> None:
    assert testSettings.hard_cap_per_employee_per_month_sgd == 20000.0


def testSoftCapMultiplierDefault(testSettings: Settings) -> None:
    assert testSettings.soft_cap_multiplier == 1.5


def testCritiqueEnabledDefault(testSettings: Settings) -> None:
    assert testSettings.compliance_critique_enabled is True


def testCritiqueTemperatureDefault(testSettings: Settings) -> None:
    assert testSettings.compliance_critique_temperature == 0.0


def testRequestGuardLimitsDefault(testSettings: Settings) -> None:
    assert testSettings.max_justification_chars == 500
    assert testSettings.max_message_chars == 2000
    assert testSettings.rate_limit_messages_per_min == 20
    assert testSettings.quota_submissions_per_day == 20
    assert testSettings.quota_retries_per_hour == 5
