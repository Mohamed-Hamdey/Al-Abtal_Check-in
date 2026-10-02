"""
AttendanceLog model — pure dataclass, no SQL.
"""

from dataclasses import dataclass
from typing import Optional


@dataclass
class AttendanceLog:
    log_id: Optional[int]
    player_id: int
    subscription_id: Optional[int]
    scan_datetime: str
    result: str
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