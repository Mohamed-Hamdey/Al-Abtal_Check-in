"""
Subscription model.

Expiry rule: configurable via config.expiry_policy —
  - "thirty_days_from_payment" (current default): expires exactly 30 days
    after the CASH PAYMENT date, not the calendar. Flexible — a payment on
    the 12th expires on the 12th of next month, not reset to the 1st.
  - "first_of_next_month" (legacy/original design): always resets to the
    1st of the month following start_date, regardless of sessions used.
Switchable per-academy in academy_config.json without touching this code.
"""

from dataclasses import dataclass
from datetime import date, timedelta
from typing import Optional
import sys
import os

sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))
from db.database import get_connection
from config.config_loader import get_plan, load_config


@dataclass
class Subscription:
    subscription_id: Optional[int]
    player_id: int
    plan_type: str
    start_date: str          # ISO date
    expiry_date: str         # ISO date, computed
    sessions_total: int
    sessions_remaining: int
    status: str = "active"   # lazy-evaluated — see logic/validation.py
    activated_by: Optional[str] = None
    payment_amount: Optional[float] = None
    payment_date: Optional[str] = None

    @classmethod
    def from_row(cls, row) -> "Subscription":
        return cls(
            subscription_id=row["subscription_id"],
            player_id=row["player_id"],
            plan_type=row["plan_type"],
            start_date=row["start_date"],
            expiry_date=row["expiry_date"],
            sessions_total=row["sessions_total"],
            sessions_remaining=row["sessions_remaining"],
            status=row["status"],
            activated_by=row["activated_by"],
            payment_amount=row["payment_amount"],
            payment_date=row["payment_date"],
        )


def compute_expiry_date(start_date: date, payment_date: date = None) -> date:
    """
    Computes expiry per the configured policy:
      - "thirty_days_from_payment": payment_date (or start_date, if no
        payment_date given) + 30 days.
      - "first_of_next_month": the 1st of the month following start_date,
        regardless of payment_date.
    """
    config = load_config()
    policy = config.get("expiry_policy", "thirty_days_from_payment")

    if policy == "first_of_next_month":
        if start_date.month == 12:
            return date(start_date.year + 1, 1, 1)
        return date(start_date.year, start_date.month + 1, 1)

    # "thirty_days_from_payment" (default)
    basis = payment_date or start_date
    return basis + timedelta(days=30)


def activate_subscription(
    player_id: int,
    plan_type: str,
    start_date: date,
    activated_by: str,
    payment_amount: float,
    payment_date: date,
) -> int:
    """
    Create a new subscription row. Renewals ALWAYS call this to create a
    fresh row rather than mutating an old one — see Decisions Log #3.
    """
    plan = get_plan(plan_type)
    expiry = compute_expiry_date(start_date, payment_date)

    conn = get_connection()
    try:
        cur = conn.execute(
            """
            INSERT INTO subscriptions
                (player_id, plan_type, start_date, expiry_date,
                 sessions_total, sessions_remaining, status,
                 activated_by, payment_amount, payment_date)
            VALUES (?, ?, ?, ?, ?, ?, 'active', ?, ?, ?)
            """,
            (
                player_id, plan_type, start_date.isoformat(), expiry.isoformat(),
                plan["sessions_total"], plan["sessions_total"],
                activated_by, payment_amount, payment_date.isoformat(),
            ),
        )
        conn.commit()
        return cur.lastrowid
    finally:
        conn.close()


def update_subscription_payment(subscription_id: int, payment_amount: float, payment_date: date) -> None:
    """
    Records a cash payment against an EXISTING subscription (e.g. the
    player paid late, or paid in person after an admin pre-activated the
    plan) — recomputes expiry from the new payment_date per the configured
    policy, and reactivates the subscription (status -> active) unless the
    freshly computed expiry has already passed.
    """
    conn = get_connection()
    try:
        row = conn.execute(
            "SELECT * FROM subscriptions WHERE subscription_id = ?", (subscription_id,)
        ).fetchone()
        if row is None:
            return
        sub = Subscription.from_row(row)

        start = date.fromisoformat(sub.start_date)
        new_expiry = compute_expiry_date(start, payment_date)
        new_status = "active" if date.today() < new_expiry else "expired"

        conn.execute(
            """
            UPDATE subscriptions
            SET payment_amount = ?, payment_date = ?, expiry_date = ?, status = ?
            WHERE subscription_id = ?
            """,
            (payment_amount, payment_date.isoformat(), new_expiry.isoformat(),
             new_status, subscription_id),
        )
        conn.commit()
    finally:
        conn.close()


def get_active_subscription(player_id: int) -> Optional[Subscription]:
    """
    Most recent subscription for a player whose stored status is still
    'active'. This is the row validate_check_in() checks against — actual
    expiry is re-derived from expiry_date at check time (lazy evaluation),
    not trusted from this stored status alone.
    """
    conn = get_connection()
    try:
        row = conn.execute(
            """
            SELECT * FROM subscriptions
            WHERE player_id = ? AND status = 'active'
            ORDER BY start_date DESC
            LIMIT 1
            """,
            (player_id,),
        ).fetchone()
        return Subscription.from_row(row) if row else None
    finally:
        conn.close()


def mark_expired(subscription_id: int) -> None:
    """Lazy status correction — called by validate_check_in() when a scan
    reveals a subscription's expiry_date has passed."""
    conn = get_connection()
    try:
        conn.execute(
            "UPDATE subscriptions SET status = 'expired' WHERE subscription_id = ?",
            (subscription_id,),
        )
        conn.commit()
    finally:
        conn.close()


def suspend_subscription(subscription_id: int) -> None:
    conn = get_connection()
    try:
        conn.execute(
            "UPDATE subscriptions SET status = 'suspended' WHERE subscription_id = ?",
            (subscription_id,),
        )
        conn.commit()
    finally:
        conn.close()


def adjust_sessions_remaining(subscription_id: int, new_value: int) -> None:
    """Manual admin correction tool — for fixing an older mis-scan."""
    conn = get_connection()
    try:
        conn.execute(
            "UPDATE subscriptions SET sessions_remaining = ? WHERE subscription_id = ?",
            (new_value, subscription_id),
        )
        conn.commit()
    finally:
        conn.close()


def decrement_session(subscription_id: int) -> None:
    conn = get_connection()
    try:
        conn.execute(
            """
            UPDATE subscriptions
            SET sessions_remaining = sessions_remaining - 1
            WHERE subscription_id = ? AND sessions_remaining > 0
            """,
            (subscription_id,),
        )
        conn.commit()
    finally:
        conn.close()


def increment_session(subscription_id: int) -> None:
    """Used by check-in undo, to restore a decremented session."""
    conn = get_connection()
    try:
        conn.execute(
            """
            UPDATE subscriptions
            SET sessions_remaining = sessions_remaining + 1
            WHERE subscription_id = ?
            """,
            (subscription_id,),
        )
        conn.commit()
    finally:
        conn.close()


def get_subscription_history(player_id: int) -> list[Subscription]:
    conn = get_connection()
    try:
        rows = conn.execute(
            """
            SELECT * FROM subscriptions
            WHERE player_id = ?
            ORDER BY start_date DESC
            """,
            (player_id,),
        ).fetchall()
        return [Subscription.from_row(r) for r in rows]
    finally:
        conn.close()


def get_display_status(player_id: int) -> dict:
    """
    Single source of truth for "what is this player's subscription situation
    right now", used by both the player list (for filtering/columns) and the
    detail screen (for the status badge). Applies the same lazy-expiry
    correction as validate_check_in — checking this counts as a "lookup" per
    spec Section 7.4, so a stale 'active' row gets corrected here too.

    Returns: {"status": "active"|"expired"|"suspended"|"none",
              "plan_type": str|None, "sessions_remaining": int|None,
              "sessions_total": int|None, "expiry_date": str|None}
    """
    from datetime import date as date_cls

    active = get_active_subscription(player_id)
    if active is not None:
        expiry = date_cls.fromisoformat(active.expiry_date)
        if date_cls.today() >= expiry:
            mark_expired(active.subscription_id)
            return {
                "status": "expired", "subscription_id": active.subscription_id,
                "plan_type": active.plan_type,
                "sessions_remaining": active.sessions_remaining,
                "sessions_total": active.sessions_total,
                "expiry_date": active.expiry_date,
            }
        return {
            "status": "active", "subscription_id": active.subscription_id,
            "plan_type": active.plan_type,
            "sessions_remaining": active.sessions_remaining,
            "sessions_total": active.sessions_total,
            "expiry_date": active.expiry_date,
        }

    history = get_subscription_history(player_id)
    if not history:
        return {"status": "none", "subscription_id": None, "plan_type": None,
                "sessions_remaining": None, "sessions_total": None, "expiry_date": None}

    latest = history[0]
    return {
        "status": latest.status, "subscription_id": latest.subscription_id,
        "plan_type": latest.plan_type,
        "sessions_remaining": latest.sessions_remaining,
        "sessions_total": latest.sessions_total,
        "expiry_date": latest.expiry_date,
    }
