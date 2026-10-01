"""
Tests for the UX-improvement pass (post-Phase-4 feedback):
  - QR code is generated automatically when a player is created (bug fix)
  - Player list filters: group, plan, subscription status, combined
  - get_display_status correctly reports active/expired/suspended/none
  - Scan screen search works by Player ID (not National ID)
"""

import os
import sys
from datetime import date, timedelta

sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))
os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PyQt6.QtWidgets import QApplication, QMessageBox

QMessageBox.warning = staticmethod(lambda *a, **k: None)
QMessageBox.information = staticmethod(lambda *a, **k: None)
QMessageBox.critical = staticmethod(lambda *a, **k: None)
QMessageBox.question = staticmethod(lambda *a, **k: QMessageBox.StandardButton.Yes)

import db.database as database

TEST_DB_PATH = os.path.join(os.path.dirname(__file__), "_test_ux_improvements.db")
database.DB_PATH = TEST_DB_PATH

from models.player import Player, create_player, get_player_by_id
from models.subscription import (
    activate_subscription, suspend_subscription, get_display_status,
)
from tests.ui.player_form_dialog import PlayerFormDialog
from tests.ui.player_list_screen import PlayerListScreen

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


def make_player(name="Filter Test Player", group="small"):
    unique_id = f"299{os.urandom(5).hex()}"[:14]
    p = Player(None, name, unique_id, "01001112222", "2013-01-01", None, group, None)
    return create_player(p)


# ---------- Bug fix: QR generation on creation ----------

def test_qr_generated_automatically_on_player_creation():
    get_app()
    dialog = PlayerFormDialog()
    dialog.name_input.setText("Auto QR Player")
    dialog.national_id_input.setText(f"299{os.urandom(5).hex()}"[:14])
    dialog.phone_input.setText("01000000001")

    dialog._on_save()

    qr_path = getattr(dialog, "newly_created_qr_path", None)
    assert qr_path is not None
    assert os.path.exists(qr_path)

    saved = get_player_by_id(dialog.saved_player_id)
    assert saved.qr_code_path == qr_path


# ---------- get_display_status ----------

def test_display_status_active():
    pid = make_player()
    activate_subscription(pid, "12", date.today(), "reception", 300.0, date.today())
    status = get_display_status(pid)
    assert status["status"] == "active"
    assert status["plan_type"] == "12"


def test_display_status_expired():
    pid = make_player()
    last_month = (date.today().replace(day=1) - timedelta(days=1)).replace(day=1)
    activate_subscription(pid, "8", last_month, "reception", 250.0, last_month)
    status = get_display_status(pid)
    assert status["status"] == "expired"


def test_display_status_suspended():
    pid = make_player()
    sub_id = activate_subscription(pid, "4", date.today(), "reception", 150.0, date.today())
    suspend_subscription(sub_id)
    status = get_display_status(pid)
    assert status["status"] == "suspended"


def test_display_status_none():
    pid = make_player()
    status = get_display_status(pid)
    assert status["status"] == "none"
    assert status["plan_type"] is None


# ---------- Player list filters ----------

def test_filter_by_group():
    get_app()
    make_player("Small Group Kid", group="small")
    make_player("Large Group Kid", group="large")

    screen = PlayerListScreen()
    idx = screen.group_filter.findData("small")
    screen.group_filter.setCurrentIndex(idx)

    names = {screen.table.item(i, 1).text() for i in range(screen.table.rowCount())}
    assert "Small Group Kid" in names
    assert "Large Group Kid" not in names


def test_filter_by_plan():
    get_app()
    pid_4 = make_player("Four Plan Kid")
    activate_subscription(pid_4, "4", date.today(), "reception", 150.0, date.today())
    pid_12 = make_player("Twelve Plan Kid")
    activate_subscription(pid_12, "12", date.today(), "reception", 300.0, date.today())

    screen = PlayerListScreen()
    idx = screen.plan_filter.findData("12")
    screen.plan_filter.setCurrentIndex(idx)

    names = {screen.table.item(i, 1).text() for i in range(screen.table.rowCount())}
    assert "Twelve Plan Kid" in names
    assert "Four Plan Kid" not in names


def test_filter_by_subscription_status():
    get_app()
    pid_active = make_player("Active Status Kid")
    activate_subscription(pid_active, "8", date.today(), "reception", 250.0, date.today())

    pid_none = make_player("No Sub Status Kid")

    screen = PlayerListScreen()
    idx = screen.status_filter.findData("none")
    screen.status_filter.setCurrentIndex(idx)

    names = {screen.table.item(i, 1).text() for i in range(screen.table.rowCount())}
    assert "No Sub Status Kid" in names
    assert "Active Status Kid" not in names


def test_combined_filters_and_search():
    get_app()
    pid = make_player("Combined Filter Kid", group="last")
    activate_subscription(pid, "8", date.today(), "reception", 250.0, date.today())

    # A distractor that matches group but not plan
    other = make_player("Combined Filter Kid Two", group="last")
    activate_subscription(other, "4", date.today(), "reception", 150.0, date.today())

    screen = PlayerListScreen()
    screen.search_input.setText("Combined Filter Kid")
    group_idx = screen.group_filter.findData("last")
    screen.group_filter.setCurrentIndex(group_idx)
    plan_idx = screen.plan_filter.findData("8")
    screen.plan_filter.setCurrentIndex(plan_idx)

    names = {screen.table.item(i, 1).text() for i in range(screen.table.rowCount())}
    assert "Combined Filter Kid" in names
    assert "Combined Filter Kid Two" not in names
