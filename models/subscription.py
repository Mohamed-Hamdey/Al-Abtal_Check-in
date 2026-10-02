"""
Subscription model — pure dataclass, no SQL.

Expiry computation and status resolution live in
services/subscription_service.py.
"""

from dataclasses import dataclass
from typing import Optional


@dataclass
class Subscription:
    subscription_id: Optional[int]
    player_id: int
    plan_type: str
    start_date: str
    expiry_date: str
    sessions_total: int
    sessions_remaining: int
    status: str = "active"
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