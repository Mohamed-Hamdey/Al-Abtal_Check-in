"""
Core check-in validation logic.

This is the part of the spec that must be bulletproof (Section 1: "strong,
correct core logic over feature breadth"). Kept deliberately free of any
UI or I/O concerns beyond simple db lookups, so it's easy to unit test in
isolation — see tests/test_validation.py.
"""

from dataclasses import dataclass
from datetime import date
from typing import Optional

import sys
import os
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from config.config_loader import get_plan
from models.subscription import Subscription, get_active_subscription, mark_expired


@dataclass
class CheckInResult:
    allowed: bool
    reason: Optional[str]        # populated when allowed=False
    subscription: Optional[Subscription]  # the subscription that was checked, if any


def validate_check_in(player_id: int, today: date) -> CheckInResult:
    """
    Runs the four gates from spec Section 4, in order:
      1. Does an active subscription exist at all?
      2. Has it passed its expiry_date? (lazy status correction happens here)
      3. Are there sessions remaining?
      4. Is today an allowed training day for this plan?
    """
    sub = get_active_subscription(player_id)

    if sub is None:
        return CheckInResult(allowed=False, reason="No active subscription", subscription=None)

    expiry = date.fromisoformat(sub.expiry_date)
    if today >= expiry:
        # Lazy evaluation: the stored status is only corrected when a scan
        # actually reveals it's stale. See spec Section 7.4.
        mark_expired(sub.subscription_id)
        sub.status = "expired"
        return CheckInResult(allowed=False, reason="Subscription expired", subscription=sub)

    if sub.sessions_remaining <= 0:
        return CheckInResult(allowed=False, reason="No sessions remaining", subscription=sub)

    plan = get_plan(sub.plan_type)
    today_name = today.strftime("%A")  # "Monday", "Friday", etc.
    if today_name not in plan["allowed_days"]:
        allowed_days_str = ", ".join(plan["allowed_days"])
        return CheckInResult(
            allowed=False,
            reason=f"Not a training day for this plan (allowed: {allowed_days_str})",
            subscription=sub,
        )

    return CheckInResult(allowed=True, reason=None, subscription=sub)
