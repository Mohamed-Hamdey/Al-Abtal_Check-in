"""
Core check-in validation logic.
"""

from dataclasses import dataclass
from datetime import date
from typing import Optional

import sys
import os
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from config.config_loader import get_plan
from models.subscription import Subscription
from services import subscription_service


@dataclass
class CheckInResult:
    allowed: bool
    reason: Optional[str]
    subscription: Optional[Subscription]


def validate_check_in(player_id: int, today: date) -> CheckInResult:
    """
    Runs the four gates from spec Section 4, in order:
      1. Does an active subscription exist at all?
      2. Has it passed its expiry_date?
      3. Are there sessions remaining?
      4. Is today an allowed training day for this plan?
    """
    sub = subscription_service.get_active(player_id)

    if sub is None:
        # Distinguish "never had a subscription" from "expired/suspended"
        history = subscription_service.get_history(player_id)
        if history and history[0].status == "expired":
            return CheckInResult(
                allowed=False, reason="Subscription expired",
                subscription=history[0],
            )
        return CheckInResult(
            allowed=False, reason="No active subscription", subscription=None
        )

    if sub.sessions_remaining <= 0:
        return CheckInResult(
            allowed=False, reason="No sessions remaining", subscription=sub
        )

    plan = get_plan(sub.plan_type)
    today_name = today.strftime("%A")
    if today_name not in plan["allowed_days"]:
        allowed_days_str = ", ".join(plan["allowed_days"])
        return CheckInResult(
            allowed=False,
            reason=f"Not a training day for this plan (allowed: {allowed_days_str})",
            subscription=sub,
        )

    return CheckInResult(allowed=True, reason=None, subscription=sub)