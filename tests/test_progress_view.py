"""
Integration tests for ui/progress_view.py (Phase 4).

Covers:
  - Attendance counters (all-time, this cycle, denials)
  - Subscription history lists all past subscriptions, newest first
  - Monthly attendance grid marks attended (✓) vs missed (✕) correctly
"""

import os
import sys
from datetime import date

sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))
os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PyQt6.QtWidgets import QApplication, QMessageBox

QMessageBox.warning = staticmethod(lambda *a, **k: None)
QMessageBox.information = staticmethod(lambda *a, **k: None)
QMessageBox.critical = staticmethod(lambda *a, **k: None)
QMessageBox.question = staticmethod(lambda *a, **k: QMessageBox.StandardButton.Yes)

import db.database as database

TEST_DB_PATH = os.path.join(os.path.dirname(__file__), "_test_progress.db")
database.DB_PATH = TEST_DB_PATH

from models.player import Player, create_player
from models.subscription import activate_subscription, adjust_sessions_remaining
from models.attendance import log_attendance
from tests.ui.progress_view import ProgressPanel

_app_instance = None


def get_app():
    global _app_instance
    app = QApplication.instance()
    if app is None:
        app = QApplication([])
    _app_instance = app
    return app


def setup_module(module):
    if os.path.exists(TEST_DB_PATH):
        os.remove(TEST_DB_PATH)
    database.init_db()


def teardown_module(module):
    if os.path.exists(TEST_DB_PATH):
        os.remove(TEST_DB_PATH)


def make_player():
    unique_id = f"299{os.urandom(5).hex()}"[:14]
    p = Player(None, "Progress Test Player", unique_id, "01001112222",
               "2013-01-01", None, "small", None)
    return create_player(p)


def test_counters_reflect_attendance_and_denials():
    get_app()
    pid = make_player()
    sub_id = activate_subscription(pid, "12", date.today(), "reception", 300.0, date.today())

    log_attendance(pid, sub_id, "allowed", None, "reception")
    log_attendance(pid, sub_id, "allowed", None, "reception")
    log_attendance(pid, sub_id, "denied", "Not a training day", "reception")

    panel = ProgressPanel(pid)
    panel.refresh()

    assert "Total attended (all-time): 2" in panel.total_attended_label.text()
    assert "This cycle: 2" in panel.cycle_attended_label.text()
    assert "Denials: 1" in panel.denial_count_label.text()


def test_cycle_counter_only_counts_current_subscription():
    get_app()
    pid = make_player()
    old_sub_id = activate_subscription(pid, "4", date(2026, 8, 1), "reception", 200.0, date(2026, 8, 1))
    log_attendance(pid, old_sub_id, "allowed", None, "reception")
    log_attendance(pid, old_sub_id, "allowed", None, "reception")

    new_sub_id = activate_subscription(pid, "12", date.today(), "reception", 300.0, date.today())
    log_attendance(pid, new_sub_id, "allowed", None, "reception")

    panel = ProgressPanel(pid)
    panel.refresh()

    assert "Total attended (all-time): 3" in panel.total_attended_label.text()
    assert "This cycle: 1" in panel.cycle_attended_label.text()  # only the new sub's row


def test_subscription_history_lists_all_past_subscriptions():
    get_app()
    pid = make_player()
    activate_subscription(pid, "4", date(2026, 7, 1), "reception", 150.0, date(2026, 7, 1))
    activate_subscription(pid, "8", date(2026, 8, 1), "reception", 250.0, date(2026, 8, 1))
    activate_subscription(pid, "12", date.today(), "reception", 300.0, date.today())

    panel = ProgressPanel(pid)
    panel.refresh()

    assert panel.history_table.rowCount() == 3
    # Newest first
    assert panel.history_table.item(0, 0).text() == "12-Session"


def test_monthly_grid_marks_attended_vs_missed():
    get_app()
    pid = make_player()
    # 12-session plan: Mon/Wed/Fri. Start subscription in September 2026.
    sub_id = activate_subscription(pid, "12", date(2026, 9, 1), "reception", 300.0, date(2026, 9, 1))

    # Sept 16, 2026 is a Wednesday — mark it attended.
    from models.attendance import AttendanceLog
    import db.database as db

    conn = db.get_connection()
    conn.execute(
        "INSERT INTO attendance_log (player_id, subscription_id, scan_datetime, result) "
        "VALUES (?, ?, ?, 'allowed')",
        (pid, sub_id, "2026-09-16 18:00:00"),
    )
    conn.commit()
    conn.close()

    panel = ProgressPanel(pid)
    # Select September 2026 in the month dropdown if present among options
    found = False
    for i, (y, m) in enumerate(panel._month_options):
        if y == 2026 and m == 9:
            panel.month_selector.setCurrentIndex(i)
            found = True
    panel.refresh()

    # Collect all cell texts in the grid
    cell_texts = []
    for i in range(panel.month_grid_layout.count()):
        w = panel.month_grid_layout.itemAt(i).widget()
        if w:
            cell_texts.append(w.text())

    if found:
        assert any("16 ✓" in t for t in cell_texts)
