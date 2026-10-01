"""
Integration tests for the Phase 3 admin tools and the new main window nav.

Covers:
  - Player list screen shows all players and supports search
  - Adding a player via PlayerFormDialog persists correctly
  - Subscription activation via SubscriptionFormDialog
  - Suspend, adjust sessions
  - Attendance undo (same-day) and manual check-in
  - MainWindow builds with two navigable pages (Check-In / Manage Players)
"""

import os
import sys
from datetime import date

sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))
os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PyQt6.QtWidgets import QApplication, QMessageBox

# QMessageBox.exec() blocks the event loop waiting for a real click, which
# never comes in an automated test — stub these out so tests don't hang.
# (question() defaults to "Yes" so suspend/reissue confirmations proceed.)
QMessageBox.warning = staticmethod(lambda *a, **k: None)
QMessageBox.information = staticmethod(lambda *a, **k: None)
QMessageBox.critical = staticmethod(lambda *a, **k: None)
QMessageBox.question = staticmethod(lambda *a, **k: QMessageBox.StandardButton.Yes)

import db.database as database

TEST_DB_PATH = os.path.join(os.path.dirname(__file__), "_test_admin_tools.db")
database.DB_PATH = TEST_DB_PATH

from models.player import Player, create_player, get_player_by_id
from models.subscription import activate_subscription, get_active_subscription, adjust_sessions_remaining
from models.attendance import log_attendance, get_attendance_for_player
from tests.ui.player_list_screen import PlayerListScreen
from tests.ui.player_detail_screen import PlayerDetailScreen
from tests.ui.player_form_dialog import PlayerFormDialog
from tests.ui.subscription_form_dialog import SubscriptionFormDialog
from tests.ui.adjust_sessions_dialog import AdjustSessionsDialog
from tests.ui.main_window import MainWindow

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


def make_player(name="Player One", group="small"):
    unique_id = f"299{os.urandom(5).hex()}"[:14]
    p = Player(None, name, unique_id, "01001112222", "2013-01-01", None, group, None)
    return create_player(p)


# ---------- Player list ----------

def test_player_list_shows_all_players():
    get_app()
    pid1 = make_player("Zainab Ali")
    pid2 = make_player("Ahmed Hassan")

    screen = PlayerListScreen()
    names = {screen.table.item(i, 1).text() for i in range(screen.table.rowCount())}

    assert "Zainab Ali" in names
    assert "Ahmed Hassan" in names


def test_player_list_search_filters_results():
    get_app()
    make_player("Unique Search Target")

    screen = PlayerListScreen()
    screen.search_input.setText("Unique Search Target")

    assert screen.table.rowCount() == 1
    assert screen.table.item(0, 1).text() == "Unique Search Target"


# ---------- Player form dialog ----------

def test_player_form_dialog_creates_player():
    get_app()
    dialog = PlayerFormDialog()
    dialog.name_input.setText("New Kid")
    dialog.national_id_input.setText(f"299{os.urandom(5).hex()}"[:14])
    dialog.phone_input.setText("01099998888")

    dialog._on_save()

    assert dialog.saved_player_id is not None
    saved = get_player_by_id(dialog.saved_player_id)
    assert saved.full_name == "New Kid"


def test_player_form_dialog_rejects_missing_fields():
    get_app()
    dialog = PlayerFormDialog()
    dialog.name_input.setText("")  # missing required field

    dialog._on_save()  # should not raise, should just not save

    assert not hasattr(dialog, "saved_player_id")


# ---------- Subscription management ----------

def test_subscription_form_activates_correctly():
    get_app()
    pid = make_player("Sub Test Player")

    dialog = SubscriptionFormDialog(pid)
    dialog.payment_amount_input.setValue(400.0)
    dialog._on_save()

    sub = get_active_subscription(pid)
    assert sub is not None
    assert sub.subscription_id == dialog.new_subscription_id
    assert sub.payment_amount == 400.0


def test_player_detail_suspend_and_adjust_sessions():
    get_app()
    pid = make_player("Detail Test Player")
    sub_id = activate_subscription(pid, "8", date.today(), "reception", 500.0, date.today())

    detail = PlayerDetailScreen(pid)
    assert detail.current_subscription.subscription_id == sub_id

    # Adjust sessions directly (bypassing the dialog's exec(), same as
    # simulating the user picking a new value and clicking Save)
    dialog = AdjustSessionsDialog(sub_id, current_value=8, total=8)
    dialog.value_input.setValue(3)
    adjust_sessions_remaining(sub_id, dialog.new_value())
    detail.refresh()

    assert detail.current_subscription.sessions_remaining == 3

    # Suspend
    from models.subscription import suspend_subscription
    suspend_subscription(sub_id)
    detail.refresh()
    assert detail.current_subscription is None  # no longer "active"
    assert "SUSPENDED" in detail.sub_status_label.text()


# ---------- Attendance correction ----------

def test_undo_same_day_checkin_restores_session():
    get_app()
    pid = make_player("Undo Test Player")
    sub_id = activate_subscription(pid, "12", date.today(), "reception", 300.0, date.today())
    adjust_sessions_remaining(sub_id, 10)

    log_id = log_attendance(pid, sub_id, "allowed", None, "reception")
    from models.subscription import decrement_session
    decrement_session(sub_id)

    detail = PlayerDetailScreen(pid)
    detail.attendance_table.selectRow(0)
    detail._on_undo_selected()

    sub = get_active_subscription(pid)
    assert sub.sessions_remaining == 10  # restored

    history = get_attendance_for_player(pid)
    assert len(history) == 0  # row deleted


def test_manual_check_in_via_detail_screen(monkeypatch):
    get_app()
    pid = make_player("Manual CheckIn Player")
    activate_subscription(pid, "12", date.today(), "reception", 300.0, date.today())

    import logic.validation as validation
    original = validation.validate_check_in
    from datetime import date as date_cls

    def forced(player_id, today):
        return original(player_id, date_cls(2026, 9, 16))  # Wednesday, allowed for plan 12

    monkeypatch.setattr("ui.checkin_service.validate_check_in", forced)

    detail = PlayerDetailScreen(pid)
    detail._on_manual_check_in()

    history = get_attendance_for_player(pid)
    assert len(history) == 1
    assert history[0].result == "allowed"


# ---------- Main window ----------

def test_main_window_has_both_nav_pages():
    get_app()
    window = MainWindow()

    assert window.nav_list.count() == 2
    assert window.nav_list.item(0).text() == "Check-In"
    assert window.nav_list.item(1).text() == "Manage Players"
    assert window.pages.count() == 2

    # Switching nav rows should switch the visible page
    window.nav_list.setCurrentRow(1)
    assert window.pages.currentWidget() is window.player_list_screen
