"""
Attendance log model.

Every scan result — allowed or denied — gets a row here. Undo is
restricted to same-day entries (Decisions Log #9) so the log stays an
honest historical record; older corrections go through
subscription.adjust_sessions_remaining() instead, leaving a visible trail.
"""

from dataclasses import dataclass
from datetime import datetime, date
from typing import Optional
import sys
import os

sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))
from db.database import get_connection
from models.subscription import increment_session


@dataclass
class AttendanceLog:
    log_id: Optional[int]
    player_id: int
    subscription_id: Optional[int]
    scan_datetime: str
    result: str                        # "allowed" / "denied"
    deny_reason: Optional[str] = None
    was_override: bool = False
    override_note: Optional[str] = None
    recorded_by: Optional[str] = None

    @classmethod
    def from_row(cls, row) -> "AttendanceLog":
        return cls(
            log_id=row["log_id"],
            player_id=row["player_id"],
            subscription_id=row["subscription_id"],
            scan_datetime=row["scan_datetime"],
            result=row["result"],
            deny_reason=row["deny_reason"],
            was_override=bool(row["was_override"]),
            override_note=row["override_note"],
            recorded_by=row["recorded_by"],
        )


def log_attendance(
    player_id: int,
    subscription_id: Optional[int],
    result: str,
    deny_reason: Optional[str],
    recorded_by: str,
    was_override: bool = False,
    override_note: Optional[str] = None,
) -> int:
    conn = get_connection()
    try:
        cur = conn.execute(
            """
            INSERT INTO attendance_log
                (player_id, subscription_id, result, deny_reason,
                 was_override, override_note, recorded_by)
            VALUES (?, ?, ?, ?, ?, ?, ?)
            """,
            (
                player_id, subscription_id, result, deny_reason,
                int(was_override), override_note, recorded_by,
            ),
        )
        conn.commit()
        return cur.lastrowid
    finally:
        conn.close()


def get_attendance_for_player(player_id: int) -> list[AttendanceLog]:
    conn = get_connection()
    try:
        rows = conn.execute(
            """
            SELECT * FROM attendance_log
            WHERE player_id = ?
            ORDER BY scan_datetime DESC
            """,
            (player_id,),
        ).fetchall()
        return [AttendanceLog.from_row(r) for r in rows]
    finally:
        conn.close()


def get_recent_attendance_with_names(limit: int = 5) -> list[dict]:
    """
    Joined query for the scan screen's "Recent Check-ins" panel — gives the
    receptionist quick context (e.g. spotting an accidental double-scan)
    without needing to open a player's full profile.
    """
    conn = get_connection()
    try:
        rows = conn.execute(
            """
            SELECT a.scan_datetime, a.result, a.deny_reason, a.was_override, p.full_name
            FROM attendance_log a
            JOIN players p ON p.player_id = a.player_id
            ORDER BY a.scan_datetime DESC
            LIMIT ?
            """,
            (limit,),
        ).fetchall()
        return [dict(r) for r in rows]
    finally:
        conn.close()


def can_undo(log_entry: AttendanceLog, today: date) -> bool:
    """Same-day-only undo window (Decisions Log #9)."""
    entry_date = datetime.fromisoformat(log_entry.scan_datetime).date()
    return entry_date == today


def undo_check_in(log_id: int, today: date) -> bool:
    """
    Reverses a check-in: deletes the log row and restores the decremented
    session. Returns False (no-op) if outside the same-day undo window.
    """
    conn = get_connection()
    try:
        row = conn.execute(
            "SELECT * FROM attendance_log WHERE log_id = ?", (log_id,)
        ).fetchone()
        if row is None:
            return False

        entry = AttendanceLog.from_row(row)
        if not can_undo(entry, today):
            return False

        if entry.result == "allowed" and entry.subscription_id is not None:
            increment_session(entry.subscription_id)

        conn.execute("DELETE FROM attendance_log WHERE log_id = ?", (log_id,))
        conn.commit()
        return True
    finally:
        conn.close()
