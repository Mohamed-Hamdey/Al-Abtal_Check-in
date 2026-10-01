"""
Player model.

A thin dataclass plus the functions that read/write the players table.
Nothing academy-specific lives here — group keys, plan types etc. are
just strings/foreign keys resolved against config_loader when needed.
"""

from dataclasses import dataclass
from typing import Optional
import sys
import os

sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))
from db.database import get_connection


@dataclass
class Player:
    player_id: Optional[int]
    full_name: str
    national_id: str
    phone: str
    dob: str                # ISO date string YYYY-MM-DD
    photo_path: Optional[str]
    player_group: str       # key into config.groups
    qr_code_path: Optional[str]
    status: str = "active"
    notes: Optional[str] = None

    @classmethod
    def from_row(cls, row) -> "Player":
        return cls(
            player_id=row["player_id"],
            full_name=row["full_name"],
            national_id=row["national_id"],
            phone=row["phone"],
            dob=row["dob"],
            photo_path=row["photo_path"],
            player_group=row["player_group"],
            qr_code_path=row["qr_code_path"],
            status=row["status"],
            notes=row["notes"],
        )


def create_player(player: Player) -> int:
    """Insert a new player, return the generated player_id."""
    conn = get_connection()
    try:
        cur = conn.execute(
            """
            INSERT INTO players
                (full_name, national_id, phone, dob, photo_path,
                 player_group, qr_code_path, status, notes)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                player.full_name, player.national_id, player.phone, player.dob,
                player.photo_path, player.player_group, player.qr_code_path,
                player.status, player.notes,
            ),
        )
        conn.commit()
        return cur.lastrowid
    finally:
        conn.close()


def get_player_by_id(player_id: int) -> Optional[Player]:
    conn = get_connection()
    try:
        row = conn.execute(
            "SELECT * FROM players WHERE player_id = ?", (player_id,)
        ).fetchone()
        return Player.from_row(row) if row else None
    finally:
        conn.close()


def get_player_by_national_id(national_id: str) -> Optional[Player]:
    """Secondary lookup — used when a QR code is lost or damaged."""
    conn = get_connection()
    try:
        row = conn.execute(
            "SELECT * FROM players WHERE national_id = ?", (national_id,)
        ).fetchone()
        return Player.from_row(row) if row else None
    finally:
        conn.close()


def list_all_players() -> list[Player]:
    """Used by the admin player list screen."""
    conn = get_connection()
    try:
        rows = conn.execute(
            "SELECT * FROM players ORDER BY full_name COLLATE NOCASE"
        ).fetchall()
        return [Player.from_row(r) for r in rows]
    finally:
        conn.close()


def search_players_by_name(name_fragment: str) -> list[Player]:
    conn = get_connection()
    try:
        rows = conn.execute(
            "SELECT * FROM players WHERE full_name LIKE ?",
            (f"%{name_fragment}%",),
        ).fetchall()
        return [Player.from_row(r) for r in rows]
    finally:
        conn.close()


def update_player(player: Player) -> None:
    conn = get_connection()
    try:
        conn.execute(
            """
            UPDATE players
            SET full_name = ?, national_id = ?, phone = ?, dob = ?,
                photo_path = ?, player_group = ?, qr_code_path = ?,
                status = ?, notes = ?
            WHERE player_id = ?
            """,
            (
                player.full_name, player.national_id, player.phone, player.dob,
                player.photo_path, player.player_group, player.qr_code_path,
                player.status, player.notes, player.player_id,
            ),
        )
        conn.commit()
    finally:
        conn.close()
