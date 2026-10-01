"""
Shared check-in pipeline.

Extracted so the camera-driven scan screen and the admin "manual check-in"
action (for a failed QR) run through exactly one code path — the logic that
decides Allowed/Denied and what gets logged must never diverge between them.
"""

import os
import sys
from datetime import date
from dataclasses import dataclass
from typing import Optional

sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from models.player import get_player_by_id, Player
from models.subscription import decrement_session, Subscription
from models.attendance import log_attendance
from logic.validation import validate_check_in
from ui.deny_popup import DenyPopup

RECORDED_BY = "reception"  # v1 has no login system; single shared identity for now


from ui.i18n import t

def _translate_reason(raw_reason: str) -> str:
    """
    Map a validation-layer reason string to a localized one. The raw reason
    comes from logic/validation.py in English; we match on substrings so
    minor wording changes there don't silently break the mapping.
    """
    r = (raw_reason or "").lower()
    if "not a training day" in r or "not a training day for this plan" in r:
        # Extract the allowed days if the caller included them, else show
        # the whole string as-is (no translation).
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
    checked_in: bool          # True if allowed, or denied-but-overridden
    reason: Optional[str]     # populated when checked_in is False
    was_override: bool


def perform_check_in(player_id: int, parent_widget=None, recorded_by: str = RECORDED_BY) -> Optional[CheckInOutcome]:
    """
    Runs the full pipeline for one player_id: validate, log, decrement,
    and — if denied — show the blocking DenyPopup modal against
    parent_widget. Returns None if the player_id doesn't exist (caller
    should show its own "unknown player" message in that case).
    """
    player = get_player_by_id(player_id)
    if player is None:
        return None

    result = validate_check_in(player_id, date.today())

    if result.allowed:
        sub_id = result.subscription.subscription_id
        log_attendance(player_id, sub_id, "allowed", None, recorded_by)
        decrement_session(sub_id)
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
        return CheckInOutcome(
            player=player, subscription=result.subscription,
            checked_in=True, reason=None, was_override=True,
        )

    log_attendance(player_id, sub_id, "denied", result.reason, recorded_by)
    return CheckInOutcome(
        player=player, subscription=result.subscription,
        checked_in=False, reason=result.reason, was_override=False,
    )
