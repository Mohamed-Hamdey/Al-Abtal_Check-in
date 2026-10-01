"""
Seed the local database with fake data for manual testing.

    python3 seed_fake_data.py          # adds fake data to the existing db
    python3 seed_fake_data.py --reset  # wipes academy.db first, then seeds

Creates a mix of players across all three groups and all three plans,
some with active subscriptions, one expired, one suspended, plus a
realistic spread of attendance history (allowed, denied, and one
overridden) so every screen in the app has something to show.
"""

import os
import sys
import argparse
from datetime import date, timedelta

sys.path.append(os.path.dirname(__file__))

from db.database import init_db, DB_PATH
from models.player import Player, create_player, update_player
from models.subscription import activate_subscription, suspend_subscription, adjust_sessions_remaining
from models.attendance import log_attendance
from logic.qr_utils import generate_qr_for_player

FAKE_PLAYERS = [
    # (name, national_id, phone, dob, group)
    ("Youssef Mostafa",  "29805120100123", "01012345001", "2013-05-12", "small"),
    ("Mariam Adel",      "29906230100456", "01012345002", "2014-06-23", "small"),
    ("Omar Khaled",      "29703140100789", "01012345003", "2012-03-14", "large"),
    ("Nour Hassan",      "29604250100321", "01012345004", "2011-04-25", "large"),
    ("Ahmed Samir",      "29508160100654", "01012345005", "2010-08-16", "large"),
    ("Laila Ibrahim",    "29409270100987", "01012345006", "2009-09-27", "last"),
    ("Kareem Tarek",     "29310080100112", "01012345007", "2008-10-08", "last"),
    ("Salma Fathy",      "29211190100334", "01012345008", "2007-11-19", "last"),
]


def seed():
    init_db()
    print(f"Seeding database at: {DB_PATH}")

    created = []
    for name, national_id, phone, dob, group in FAKE_PLAYERS:
        player = Player(None, name, national_id, phone, dob, None, group, None)
        pid = create_player(player)
        qr_path = generate_qr_for_player(pid)
        # BUG FIX (same class as the player_form_dialog bug): generating the
        # QR file isn't enough — the player row's qr_code_path must be
        # updated too, or the app has no idea the file exists.
        player.player_id = pid
        player.qr_code_path = qr_path
        update_player(player)
        created.append((pid, name))
        print(f"  + Player: {name} (id={pid}, group={group})")

    today = date.today()

    # --- Player 1: active 12-session plan, several attended sessions ---
    pid1, _ = created[0]
    sub1 = activate_subscription(pid1, "12", today - timedelta(days=5), "reception", 300.0, today - timedelta(days=5))
    log_attendance(pid1, sub1, "allowed", None, "reception")
    log_attendance(pid1, sub1, "allowed", None, "reception")
    adjust_sessions_remaining(sub1, 10)

    # --- Player 2: active 8-session plan, one denied (wrong day) ---
    pid2, _ = created[1]
    sub2 = activate_subscription(pid2, "8", today - timedelta(days=2), "reception", 250.0, today - timedelta(days=2))
    log_attendance(pid2, sub2, "denied", "Not a training day for this plan", "reception")

    # --- Player 3: active 4-session plan, one overridden check-in ---
    pid3, _ = created[2]
    sub3 = activate_subscription(pid3, "4", today - timedelta(days=1), "reception", 150.0, today - timedelta(days=1))
    log_attendance(pid3, sub3, "allowed", None, "reception",
                    was_override=True, override_note="Coach approved makeup session")
    adjust_sessions_remaining(sub3, 3)

    # --- Player 4: EXPIRED subscription (started last month) ---
    pid4, _ = created[3]
    last_month_start = (today.replace(day=1) - timedelta(days=1)).replace(day=1)
    sub4 = activate_subscription(pid4, "12", last_month_start, "reception", 300.0, last_month_start)
    log_attendance(pid4, sub4, "allowed", None, "reception")

    # --- Player 5: SUSPENDED subscription ---
    pid5, _ = created[4]
    sub5 = activate_subscription(pid5, "8", today - timedelta(days=3), "reception", 250.0, today - timedelta(days=3))
    suspend_subscription(sub5)

    # --- Player 6: no sessions remaining ---
    pid6, _ = created[5]
    sub6 = activate_subscription(pid6, "4", today - timedelta(days=4), "reception", 150.0, today - timedelta(days=4))
    adjust_sessions_remaining(sub6, 0)

    # --- Player 7 & 8: no subscription at all yet (fresh onboarding case) ---
    # (created above, intentionally left without activate_subscription)

    print("\nDone. Summary:")
    print(f"  {len(created)} players created")
    print("  Player 1 (Youssef): active 12-session, 2 attended")
    print("  Player 2 (Mariam): active 8-session, 1 denied (wrong day)")
    print("  Player 3 (Omar): active 4-session, 1 overridden check-in")
    print("  Player 4 (Nour): EXPIRED subscription")
    print("  Player 5 (Ahmed): SUSPENDED subscription")
    print("  Player 6 (Laila): 0 sessions remaining")
    print("  Player 7 (Kareem), Player 8 (Salma): no subscription yet")
    print("\nQR codes generated under assets/qr_codes/player_<id>.png")
    print("Open the app (python3 main.py) and check Manage Players to explore.")


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--reset", action="store_true", help="Wipe academy.db before seeding")
    args = parser.parse_args()

    if args.reset and os.path.exists(DB_PATH):
        os.remove(DB_PATH)
        print(f"Removed existing database at {DB_PATH}")

    seed()
