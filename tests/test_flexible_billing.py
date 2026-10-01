"""
Tests for:
  - compute_expiry_date under both configured policies
    ("thirty_days_from_payment" default, and legacy "first_of_next_month")
  - update_subscription_payment: recording a cash payment reactivates an
    expired/suspended subscription and recomputes its expiry
"""

import os
import sys
from datetime import date, timedelta

sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

import db.database as database

TEST_DB_PATH = os.path.join(os.path.dirname(__file__), "_test_billing.db")
database.DB_PATH = TEST_DB_PATH

import config.config_loader as config_loader
from models.player import Player, create_player
from models.subscription import (
    compute_expiry_date, activate_subscription, update_subscription_payment,
    suspend_subscription, get_display_status, mark_expired, get_active_subscription,
)


def setup_module(module):
    if os.path.exists(TEST_DB_PATH):
        os.remove(TEST_DB_PATH)
    database.init_db()


def teardown_module(module):
    if os.path.exists(TEST_DB_PATH):
        os.remove(TEST_DB_PATH)


def make_player():
    unique_id = f"299{os.urandom(5).hex()}"[:14]
    p = Player(None, "Billing Test Player", unique_id, "01001112222", "2013-01-01", None, "small", None)
    return create_player(p)


def with_policy(policy: str, fn):
    """Temporarily override the loaded config's expiry_policy for one call."""
    original = config_loader.load_config()
    original_policy = original.get("expiry_policy")
    original["expiry_policy"] = policy
    try:
        return fn()
    finally:
        original["expiry_policy"] = original_policy


# ---------- compute_expiry_date policies ----------

def test_thirty_days_from_payment_uses_payment_date_not_start_date():
    start = date(2026, 9, 1)
    payment = date(2026, 9, 15)  # paid two weeks after "starting"
    expiry = with_policy("thirty_days_from_payment", lambda: compute_expiry_date(start, payment))
    assert expiry == date(2026, 10, 15)  # 30 days from PAYMENT, not start


def test_thirty_days_falls_back_to_start_date_if_no_payment_date_given():
    start = date(2026, 9, 1)
    expiry = with_policy("thirty_days_from_payment", lambda: compute_expiry_date(start))
    assert expiry == date(2026, 10, 1)


def test_first_of_next_month_policy_ignores_payment_date():
    start = date(2026, 9, 20)
    payment = date(2026, 9, 25)  # should be irrelevant under this policy
    expiry = with_policy("first_of_next_month", lambda: compute_expiry_date(start, payment))
    assert expiry == date(2026, 10, 1)


def test_first_of_next_month_december_rolls_year():
    start = date(2026, 12, 15)
    expiry = with_policy("first_of_next_month", lambda: compute_expiry_date(start))
    assert expiry == date(2027, 1, 1)


# ---------- update_subscription_payment ----------

def test_recording_payment_reactivates_expired_subscription():
    pid = make_player()
    old_start = date.today() - timedelta(days=60)
    sub_id = activate_subscription(pid, "8", old_start, "reception", 250.0, old_start)
    mark_expired(sub_id)  # simulate it having gone stale

    status_before = get_display_status(pid)
    assert status_before["status"] == "expired"

    update_subscription_payment(sub_id, 250.0, date.today())

    status_after = get_display_status(pid)
    assert status_after["status"] == "active"
    assert status_after["expiry_date"] == (date.today() + timedelta(days=30)).isoformat()


def test_recording_payment_reactivates_suspended_subscription():
    pid = make_player()
    sub_id = activate_subscription(pid, "4", date.today(), "reception", 150.0, date.today())
    suspend_subscription(sub_id)

    status_before = get_display_status(pid)
    assert status_before["status"] == "suspended"

    update_subscription_payment(sub_id, 150.0, date.today())

    status_after = get_display_status(pid)
    assert status_after["status"] == "active"


def test_recording_payment_with_past_date_stays_expired():
    """A backdated payment that's still >30 days old shouldn't falsely
    reactivate the subscription — recomputed expiry must still be checked
    against today."""
    pid = make_player()
    sub_id = activate_subscription(pid, "4", date.today(), "reception", 150.0, date.today())

    very_old_payment = date.today() - timedelta(days=100)
    update_subscription_payment(sub_id, 150.0, very_old_payment)

    status_after = get_display_status(pid)
    assert status_after["status"] == "expired"


def test_recording_payment_updates_amount_and_date():
    pid = make_player()
    sub_id = activate_subscription(pid, "12", date.today(), "reception", 300.0, date.today())

    new_payment_date = date.today()
    update_subscription_payment(sub_id, 999.0, new_payment_date)

    sub = get_active_subscription(pid)
    assert sub.payment_amount == 999.0
    assert sub.payment_date == new_payment_date.isoformat()
