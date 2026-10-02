"""
Attendance service — check-in logging and undo rules.
"""

import os
import sys
from datetime import date, datetime

sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))
from models.attendance import AttendanceLog
from repositories import attendance_repo
from services import subscription_service


def log_attendance(
    player_id: int,
    subscription_id: "int | None",
    result: str,
    deny_reason: "str | None",
    recorded_by: str,
    was_override: bool = False,
    override_note: "str | None" = None,
    scan_datetime: "str | None" = None,
) -> int:
    return attendance_repo.log(
        player_id, subscription_id, result, deny_reason,
        recorded_by, was_override=was_override, override_note=override_note,
        scan_datetime=scan_datetime,
    )
def get_for_player(player_id: int) -> list[AttendanceLog]:
    return attendance_repo.get_for_player(player_id)


def get_recent_with_names(limit: int = 5) -> list[dict]:
    return attendance_repo.get_recent_with_names(limit=limit)


def has_checked_in_today(player_id: int, on_date: "date | None" = None) -> bool:
    """
    True if the player already has an 'allowed' entry dated on_date
    (defaults to today, in LOCAL time).
    Denied entries don't count — that way a denial in the morning doesn't
    block a check-in after the receptionist fixes the account.
    """
    if on_date is None:
        on_date = date.today()
    return attendance_repo.has_allowed_entry_on(player_id, on_date)
def can_undo(log_entry: AttendanceLog, today: date) -> bool:
    """Same-day-only undo window."""
    entry_date = datetime.fromisoformat(log_entry.scan_datetime).date()
    return entry_date == today


def undo_check_in(log_id: int, today: date) -> bool:
    """
    Reverses a check-in: deletes the log row and restores the decremented
    session. Returns False if outside the same-day undo window.
    """
    entry = attendance_repo.get_by_id(log_id)
    if entry is None:
        return False
    if not can_undo(entry, today):
        return False

    if entry.result == "allowed" and entry.subscription_id is not None:
        subscription_service.increment_session(entry.subscription_id)

    attendance_repo.delete(log_id)
    return True