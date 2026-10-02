"""
End-to-end tests for the check-in pipeline.

Run with:
    pytest tests/test_checkin_flow.py -v
"""

import os
import sys
import sqlite3
import tempfile
from datetime import date, datetime, timedelta

import pytest

# Make the project root importable regardless of where pytest is invoked
# from. This must run before any app imports (which are done lazily,
# inside fixtures and tests, to avoid collection-time errors).
_PROJECT_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
if _PROJECT_ROOT not in sys.path:
    sys.path.insert(0, _PROJECT_ROOT)


# A fixed "today" that is a Monday. 2025-01-06 was a Monday.
TEST_TODAY = date(2025, 1, 6)
TEST_NOW = datetime(2025, 1, 6, 14, 30, 0)


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

@pytest.fixture
def temp_db(monkeypatch):
    """Create a fresh temporary database for each test."""
    import db.database as db_module

    tmpdir = tempfile.mkdtemp(prefix="academy_test_")
    db_file = os.path.join(tmpdir, "test.db")

    monkeypatch.setattr(db_module, "DB_PATH", db_file)

    with open(db_module.SCHEMA_PATH, "r", encoding="utf-8") as f:
        schema = f.read()

    conn = sqlite3.connect(db_file)
    try:
        conn.executescript(schema)
        conn.commit()
    finally:
        conn.close()

    yield db_file

    try:
        os.remove(db_file)
        os.rmdir(tmpdir)
    except Exception:
        pass


@pytest.fixture
def frozen_today(monkeypatch):
    """
    Freeze date.today() and datetime.now() in every module on the
    check-in path so tests are deterministic.
    """
    class FakeDate(date):
        @classmethod
        def today(cls):
            return TEST_TODAY

    class FakeDatetime(datetime):
        @classmethod
        def now(cls, tz=None):
            return TEST_NOW

    import services.checkin_service as checkin_mod
    import services.subscription_service as sub_mod
    import services.attendance_service as att_mod
    import repositories.attendance_repo as att_repo_mod
    import logic.validation as val_mod

    for mod in (checkin_mod, sub_mod, att_mod, att_repo_mod, val_mod):
        if hasattr(mod, "date"):
            monkeypatch.setattr(mod, "date", FakeDate, raising=False)
        if hasattr(mod, "datetime"):
            monkeypatch.setattr(mod, "datetime", FakeDatetime, raising=False)


@pytest.fixture
def fake_deny_popup(monkeypatch):
    """Make DenyPopup.exec() return immediately without a UI."""
    import services.checkin_service as checkin_mod

    class FakePopup:
        def __init__(self, *args, **kwargs):
            pass
        def exec(self):
            return 0
        def result_data(self):
            return (False, None)

    monkeypatch.setattr(checkin_mod, "DenyPopup", FakePopup, raising=False)


# ---------------------------------------------------------------------------
# DB helpers
# ---------------------------------------------------------------------------

def _insert_player(db_file, full_name="Test Player", group="small"):
    conn = sqlite3.connect(db_file)
    try:
        cur = conn.execute(
            """
            INSERT INTO players
                (full_name, national_id, phone, dob, photo_path,
                 player_group, qr_code_path, status, notes)
            VALUES (?, NULL, ?, ?, NULL, ?, NULL, 'active', NULL)
            """,
            (full_name, "01000000000", "2015-01-01", group),
        )
        conn.commit()
        return cur.lastrowid
    finally:
        conn.close()


def _insert_subscription(
    db_file,
    player_id,
    plan_type="8",
    sessions_remaining=8,
    sessions_total=8,
    status="active",
    expiry_offset_days=30,
):
    expiry = (TEST_TODAY + timedelta(days=expiry_offset_days)).isoformat()
    start = TEST_TODAY.isoformat()
    conn = sqlite3.connect(db_file)
    try:
        cur = conn.execute(
            """
            INSERT INTO subscriptions
                (player_id, plan_type, start_date, expiry_date,
                 sessions_total, sessions_remaining, status,
                 activated_by, payment_amount, payment_date)
            VALUES (?, ?, ?, ?, ?, ?, ?, 'test', 0, ?)
            """,
            (player_id, plan_type, start, expiry,
             sessions_total, sessions_remaining, status, start),
        )
        conn.commit()
        return cur.lastrowid
    finally:
        conn.close()


def _get_sessions(db_file, subscription_id):
    conn = sqlite3.connect(db_file)
    try:
        row = conn.execute(
            "SELECT sessions_remaining FROM subscriptions WHERE subscription_id = ?",
            (subscription_id,),
        ).fetchone()
        return row[0] if row else None
    finally:
        conn.close()


def _get_attendance_rows(db_file, player_id):
    conn = sqlite3.connect(db_file)
    conn.row_factory = sqlite3.Row
    try:
        rows = conn.execute(
            "SELECT * FROM attendance_log WHERE player_id = ? ORDER BY log_id",
            (player_id,),
        ).fetchall()
        return [dict(r) for r in rows]
    finally:
        conn.close()


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------

class TestBasicCheckIn:
    def test_allowed_checkin_decrements_and_logs(self, temp_db, frozen_today, fake_deny_popup):
        from services.checkin_service import perform_check_in

        player_id = _insert_player(temp_db)
        sub_id = _insert_subscription(temp_db, player_id, sessions_remaining=8)

        outcome = perform_check_in(player_id, parent_widget=None)

        assert outcome is not None
        assert outcome.checked_in is True
        assert outcome.was_override is False
        assert outcome.was_duplicate is False

        assert _get_sessions(temp_db, sub_id) == 7

        rows = _get_attendance_rows(temp_db, player_id)
        assert len(rows) == 1
        assert rows[0]["result"] == "allowed"

    def test_second_scan_same_day_is_duplicate(self, temp_db, frozen_today, fake_deny_popup):
        from services.checkin_service import perform_check_in

        player_id = _insert_player(temp_db)
        sub_id = _insert_subscription(temp_db, player_id, sessions_remaining=8)

        first = perform_check_in(player_id, parent_widget=None)
        assert first.checked_in is True
        assert first.was_duplicate is False
        assert _get_sessions(temp_db, sub_id) == 7

        second = perform_check_in(player_id, parent_widget=None)
        assert second is not None
        assert second.was_duplicate is True

        assert _get_sessions(temp_db, sub_id) == 7
        assert len(_get_attendance_rows(temp_db, player_id)) == 1

    def test_unknown_player_returns_none(self, temp_db, frozen_today, fake_deny_popup):
        from services.checkin_service import perform_check_in
        outcome = perform_check_in(99999, parent_widget=None)
        assert outcome is None


class TestDenials:
    def test_expired_subscription_denied(self, temp_db, frozen_today, fake_deny_popup):
        from services.checkin_service import perform_check_in

        player_id = _insert_player(temp_db)
        sub_id = _insert_subscription(temp_db, player_id, expiry_offset_days=-1)

        outcome = perform_check_in(player_id, parent_widget=None)

        assert outcome is not None
        assert outcome.checked_in is False
        assert _get_sessions(temp_db, sub_id) == 8

        rows = _get_attendance_rows(temp_db, player_id)
        assert len(rows) == 1
        assert rows[0]["result"] == "denied"

    def test_suspended_subscription_denied(self, temp_db, frozen_today, fake_deny_popup):
        from services.checkin_service import perform_check_in

        player_id = _insert_player(temp_db)
        sub_id = _insert_subscription(temp_db, player_id, status="suspended")

        outcome = perform_check_in(player_id, parent_widget=None)

        assert outcome.checked_in is False
        assert _get_sessions(temp_db, sub_id) == 8

    def test_no_sessions_remaining_denied(self, temp_db, frozen_today, fake_deny_popup):
        from services.checkin_service import perform_check_in

        player_id = _insert_player(temp_db)
        sub_id = _insert_subscription(temp_db, player_id, sessions_remaining=0)

        outcome = perform_check_in(player_id, parent_widget=None)

        assert outcome.checked_in is False


class TestOverride:
    def test_override_logs_and_decrements(self, temp_db, frozen_today, monkeypatch):
        from services.checkin_service import perform_check_in
        import services.checkin_service as checkin_mod

        player_id = _insert_player(temp_db)
        sub_id = _insert_subscription(temp_db, player_id, expiry_offset_days=-1)

        class OverridePopup:
            def __init__(self, *args, **kwargs):
                pass
            def exec(self):
                return 0
            def result_data(self):
                return (True, "Test override")

        monkeypatch.setattr(checkin_mod, "DenyPopup", OverridePopup, raising=False)

        outcome = perform_check_in(player_id, parent_widget=None)

        assert outcome is not None
        assert outcome.checked_in is True
        assert outcome.was_override is True
        assert _get_sessions(temp_db, sub_id) == 7

        rows = _get_attendance_rows(temp_db, player_id)
        assert len(rows) == 1
        assert rows[0]["result"] == "allowed"
        assert rows[0]["was_override"] == 1
        assert rows[0]["override_note"] == "Test override"


class TestUndo:
    def test_undo_restores_session(self, temp_db, frozen_today, fake_deny_popup):
        from services.checkin_service import perform_check_in
        from services import attendance_service

        player_id = _insert_player(temp_db)
        sub_id = _insert_subscription(temp_db, player_id, sessions_remaining=8)

        perform_check_in(player_id, parent_widget=None)
        assert _get_sessions(temp_db, sub_id) == 7

        rows = _get_attendance_rows(temp_db, player_id)
        log_id = rows[0]["log_id"]

        ok = attendance_service.undo_check_in(log_id, TEST_TODAY)
        assert ok is True

        assert _get_sessions(temp_db, sub_id) == 8
        assert len(_get_attendance_rows(temp_db, player_id)) == 0