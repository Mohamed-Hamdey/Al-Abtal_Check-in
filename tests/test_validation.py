"""
Unit tests for logic/validation.py — the core rule that decides whether a
player can train today. This is intentionally tested in isolation from the
database and UI, using a fake subscription object and monkeypatching the
one db lookup function, so these tests run fast and don't need a real
academy.db file.

Run with:  pytest tests/test_validation.py -v
"""

import sys
import os
from datetime import date

sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

import logic.validation as validation
from models.subscription import Subscription


def make_fake_subscription(**overrides) -> Subscription:
    """A default valid subscription, with fields overridable per test."""
    defaults = dict(
        subscription_id=1,
        player_id=1,
        plan_type="8",
        start_date="2026-09-01",
        expiry_date="2026-10-01",
        sessions_total=8,
        sessions_remaining=5,
        status="active",
        activated_by="reception",
        payment_amount=500.0,
        payment_date="2026-09-01",
    )
    defaults.update(overrides)
    return Subscription(**defaults)


def test_no_subscription_is_denied(monkeypatch):
    monkeypatch.setattr(validation, "get_active_subscription", lambda pid: None)

    result = validation.validate_check_in(player_id=1, today=date(2026, 9, 15))

    assert result.allowed is False
    assert result.reason == "No active subscription"


def test_expired_subscription_is_denied(monkeypatch):
    sub = make_fake_subscription(expiry_date="2026-09-01")
    monkeypatch.setattr(validation, "get_active_subscription", lambda pid: sub)
    monkeypatch.setattr(validation, "mark_expired", lambda sub_id: None)

    # today == expiry_date should already be treated as expired (>=)
    result = validation.validate_check_in(player_id=1, today=date(2026, 9, 1))

    assert result.allowed is False
    assert result.reason == "Subscription expired"


def test_mid_month_start_still_expires_first_of_next_month(monkeypatch):
    # A subscription started Sept 20 should behave identically to one
    # started Sept 1 — both expire Oct 1, no pro-rating (Decisions Log #1).
    sub = make_fake_subscription(start_date="2026-09-20", expiry_date="2026-10-01")
    monkeypatch.setattr(validation, "get_active_subscription", lambda pid: sub)

    # Sept 30 — should still be allowed (day-of-week permitting)
    result_before = validation.validate_check_in(player_id=1, today=date(2026, 9, 30))
    assert result_before.reason != "Subscription expired"

    # Oct 1 — should now be denied
    monkeypatch.setattr(validation, "mark_expired", lambda sub_id: None)
    result_after = validation.validate_check_in(player_id=1, today=date(2026, 10, 1))
    assert result_after.allowed is False
    assert result_after.reason == "Subscription expired"


def test_no_sessions_remaining_is_denied(monkeypatch):
    sub = make_fake_subscription(sessions_remaining=0)
    monkeypatch.setattr(validation, "get_active_subscription", lambda pid: sub)

    result = validation.validate_check_in(player_id=1, today=date(2026, 9, 18))  # a Friday

    assert result.allowed is False
    assert result.reason == "No sessions remaining"


def test_wrong_day_is_denied(monkeypatch):
    # 4-session plan only allows Friday
    sub = make_fake_subscription(plan_type="4")
    monkeypatch.setattr(validation, "get_active_subscription", lambda pid: sub)

    # Sept 16, 2026 is a Wednesday
    result = validation.validate_check_in(player_id=1, today=date(2026, 9, 16))

    assert result.allowed is False
    assert "Not a training day" in result.reason


def test_valid_check_in_is_allowed(monkeypatch):
    # 12-session plan allows Monday/Wednesday/Friday
    sub = make_fake_subscription(plan_type="12", sessions_remaining=10)
    monkeypatch.setattr(validation, "get_active_subscription", lambda pid: sub)

    # Sept 16, 2026 is a Wednesday
    result = validation.validate_check_in(player_id=1, today=date(2026, 9, 16))

    assert result.allowed is True
    assert result.reason is None
    assert result.subscription.subscription_id == sub.subscription_id


def test_gates_checked_in_correct_order(monkeypatch):
    # A subscription that is BOTH expired AND has 0 sessions remaining
    # should report "expired" first, since expiry is checked before
    # sessions_remaining in validate_check_in().
    sub = make_fake_subscription(expiry_date="2026-09-01", sessions_remaining=0)
    monkeypatch.setattr(validation, "get_active_subscription", lambda pid: sub)
    monkeypatch.setattr(validation, "mark_expired", lambda sub_id: None)

    result = validation.validate_check_in(player_id=1, today=date(2026, 9, 15))

    assert result.reason == "Subscription expired"
