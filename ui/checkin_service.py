"""
Shared check-in pipeline.

Policy: a player may be checked in at most once per calendar day.
A second scan of the same player on the same day is refused with a
"already checked in today" message; no attendance row is logged and no
session is decremented.
"""

import os
import sys
from datetime import date
from dataclasses import dataclass
from typing import Optional

sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from models.player import get_player_by_id, Player
from models.subscription import decrement_session, Subscription
from models.attendance import log_attendance, has_checked_in_today
from logic.validation import validate_check_in
from ui.deny_popup import DenyPopup
from ui.i18n import t

RECORDED_BY = "reception"


def _translate_reason(raw_reason: str) -> str:
    """Map validation-layer English reason to a localized string."""
    r = (raw_reason or "").lower()
    if "not a training day" in r:
        if "allowed:" in r:
            days = raw_reason.split("allowed:", 1)[1].strip().rstrip(")")
            return t("reason.not_a_training_day", days=days)
        return raw_reason
    if "no sessions" in r:
        return t("reason.no_sessions")
    if "expired" in r:
        return t("reason.expired")
    if "suspended" in r:
        return t("reason.suspended")
    if "no subscription" in r or "no active subscription" in r:
        return t("reason.no_subscription")
    return raw_reason


@dataclass
class CheckInOutcome:
    player: Player
    subscription: Optional[Subscription]
    checked_in: bool
    reason: Optional[str]
    was_override: bool
    # True when the scan was refused because the player already checked
    # in today. The caller shows an informational message but takes no
    # other action.
    was_duplicate: bool = False


def perform_check_in(
    player_id: int,
    parent_widget=None,
    recorded_by: str = RECORDED_BY,
) -> Optional[CheckInOutcome]:
    """
    Runs the full pipeline for one player_id.

    Returns None if the player doesn't exist.
    Returns an outcome with was_duplicate=True if the player was already
    checked in today — caller should show an informational message.
    """
    player = get_player_by_id(player_id)
    if player is None:
        return None

    # --- Once-per-day guard ---------------------------------------------
    # If the player already has an 'allowed' attendance entry dated today,
    # refuse this scan: no logging, no decrement, no popup.
    if has_checked_in_today(player_id):
        return CheckInOutcome(
            player=player,
            subscription=None,
            checked_in=True,
            reason=None,
            was_override=False,
            was_duplicate=True,
        )

    result = validate_check_in(player_id, date.today())

    if result.allowed:
        sub_id = result.subscription.subscription_id
        log_attendance(player_id, sub_id, "allowed", None, recorded_by)
        decrement_session(sub_id)
        # Keep the in-memory copy in sync so the UI shows the new count.
        result.subscription.sessions_remaining = max(
            0, result.subscription.sessions_remaining - 1
        )
        return CheckInOutcome(
            player=player, subscription=result.subscription,
            checked_in=True, reason=None, was_override=False,
        )

    popup = DenyPopup(player.full_name, _translate_reason(result.reason), parent_widget)
    popup.exec()
    was_override, note = popup.result_data()

    sub_id = result.subscription.subscription_id if result.subscription else None

    if was_override:
        log_attendance(player_id, sub_id, "allowed", None, recorded_by,
                        was_override=True, override_note=note)
        if sub_id is not None:
            decrement_session(sub_id)
            if result.subscription is not None:
                result.subscription.sessions_remaining = max(
                    0, result.subscription.sessions_remaining - 1
                )
        return CheckInOutcome(
            player=player, subscription=result.subscription,
            checked_in=True, reason=None, was_override=True,
        )

    log_attendance(player_id, sub_id, "denied", result.reason, recorded_by)
    return CheckInOutcome(
        player=player, subscription=result.subscription,
        checked_in=False, reason=result.reason, was_override=False,
    )