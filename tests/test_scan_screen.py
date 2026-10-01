"""
Integration test for ui/scan_screen.py.

Runs the real PyQt6 widgets (offscreen) against a temporary SQLite database,
driving handle_player_id() directly to simulate what a camera scan or
manual search selection would trigger. Covers:
  1. Allowed check-in -> card shows "Checked in", session decremented, row logged
  2. Denied + Dismiss -> no session change, denied row logged
  3. Denied + Override -> session decremented, override row logged with note

The DenyPopup is auto-answered by monkeypatching QDialog.exec so this runs
without a human clicking anything.
"""

import os
import sys
from datetime import date

sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PyQt6.QtWidgets import QApplication
from PyQt6.QtCore import Qt

import db.database as database

# Point the db module at a throwaway test file before anything else imports it
TEST_DB_PATH = os.path.join(os.path.dirname(__file__), "_test_scan_screen.db")
database.DB_PATH = TEST_DB_PATH

from models.player import Player, create_player
from models.subscription import activate_subscription, get_active_subscription
from models.attendance import get_attendance_for_player
from tests.ui.scan_screen import ScanScreen
from tests.ui.deny_popup import DenyPopup


def setup_module(module):
    if os.path.exists(TEST_DB_PATH):
        os.remove(TEST_DB_PATH)
    database.init_db()


def teardown_module(module):
    if os.path.exists(TEST_DB_PATH):
        os.remove(TEST_DB_PATH)


def make_player_with_plan(plan_type, sessions_remaining_override=None, start_date=None):
    p = Player(None, "Ahmed Test", f"2990101011{os.urandom(2).hex()}", "01001112222",
               "2013-01-01", None, "small", None)
    pid = create_player(p)
    sub_id = activate_subscription(
        pid, plan_type, start_date or date.today(), "reception", 300.0, date.today()
    )
    if sessions_remaining_override is not None:
        from models.subscription import adjust_sessions_remaining
        adjust_sessions_remaining(sub_id, sessions_remaining_override)
    return pid, sub_id


# Held at module scope — without a live reference, PyQt6 garbage-collects
# the QApplication instance immediately and every subsequent QWidget()
# construction fails with "Must construct a QApplication before a QWidget".
_app_instance = None


def get_app():
    global _app_instance
    app = QApplication.instance()
    if app is None:
        app = QApplication([])
    _app_instance = app
    return app


def test_allowed_check_in_updates_ui_and_db(monkeypatch):
    get_app()

    # 12-session plan allows Mon/Wed/Fri — pick a day guaranteed to match
    # by testing against whatever plan_type is valid today. Simplify by
    # using the "12" plan and finding the next allowed weekday for the
    # assertion instead of forcing today.
    pid, sub_id = make_player_with_plan("12")

    screen = ScanScreen()

    # Force validate_check_in's day check to pass regardless of what day
    # the test happens to run on, by monkeypatching date.today() used
    # inside logic.validation via freezing "today" — simplest path here is
    # to monkeypatch validate_check_in directly with a controlled date.
    import logic.validation as validation
    original = validation.validate_check_in
    from datetime import date as date_cls

    def forced(player_id, today):
        # Wednesday 2026-09-16 is allowed for all plan types
        return original(player_id, date_cls(2026, 9, 16))

    monkeypatch.setattr("ui.checkin_service.validate_check_in", forced)

    screen.handle_player_id(pid)

    assert screen.player_card.status_label.text() == "Checked in ✓"

    sub = get_active_subscription(pid)
    assert sub.sessions_remaining == 11  # 12 - 1

    history = get_attendance_for_player(pid)
    assert len(history) == 1
    assert history[0].result == "allowed"


def test_denied_and_dismissed_does_not_change_sessions(monkeypatch):
    get_app()

    # 4-session plan only allows Friday — force a Wednesday to guarantee denial
    pid, sub_id = make_player_with_plan("4")

    import logic.validation as validation
    original = validation.validate_check_in
    from datetime import date as date_cls

    def forced(player_id, today):
        return original(player_id, date_cls(2026, 9, 16))  # Wednesday

    monkeypatch.setattr("ui.checkin_service.validate_check_in", forced)

    # Auto-dismiss: simulate the popup's Dismiss button being pressed
    def fake_exec(self):
        self.reject()
        return 0

    monkeypatch.setattr(DenyPopup, "exec", fake_exec)

    screen = ScanScreen()
    screen.handle_player_id(pid)

    sub = get_active_subscription(pid)
    assert sub.sessions_remaining == 4  # unchanged

    history = get_attendance_for_player(pid)
    assert len(history) == 1
    assert history[0].result == "denied"
    assert history[0].was_override is False


def test_denied_and_overridden_decrements_and_logs_note(monkeypatch):
    get_app()

    pid, sub_id = make_player_with_plan("4")

    import logic.validation as validation
    original = validation.validate_check_in
    from datetime import date as date_cls

    def forced(player_id, today):
        return original(player_id, date_cls(2026, 9, 16))  # Wednesday, denied

    monkeypatch.setattr("ui.checkin_service.validate_check_in", forced)

    # Auto-override: simulate typing a note and clicking Override
    def fake_exec(self):
        self.note_input.setText("Coach approved makeup session")
        self._on_override_clicked()
        return 1

    monkeypatch.setattr(DenyPopup, "exec", fake_exec)

    screen = ScanScreen()
    screen.handle_player_id(pid)

    sub = get_active_subscription(pid)
    assert sub.sessions_remaining == 3  # decremented despite denial

    history = get_attendance_for_player(pid)
    assert len(history) == 1
    assert history[0].result == "allowed"
    assert history[0].was_override is True
    assert history[0].override_note == "Coach approved makeup session"


def test_manual_search_by_player_id_finds_player():
    get_app()
    pid, _ = make_player_with_plan("8")
    from models.player import get_player_by_id
    player = get_player_by_id(pid)

    screen = ScanScreen()
    screen.search_input.setText(str(player.player_id))
    screen._on_manual_search()

    assert screen.results_list.count() == 1
    assert player.full_name in screen.results_list.item(0).text()


def test_manual_search_by_name_finds_player():
    get_app()
    pid, _ = make_player_with_plan("8")
    from models.player import get_player_by_id
    player = get_player_by_id(pid)

    screen = ScanScreen()
    screen.search_input.setText(player.full_name)
    screen._on_manual_search()

    # Other tests in this module share the same test DB and default name
    # ("Ahmed Test"), so a name search may legitimately match more than
    # one player — just confirm THIS player's ID is among the results.
    assert screen.results_list.count() >= 1
    matching_ids = [
        screen.results_list.item(i).data(Qt.ItemDataRole.UserRole)
        for i in range(screen.results_list.count())
    ]
    assert player.player_id in matching_ids
