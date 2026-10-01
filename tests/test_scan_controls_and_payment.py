"""
Tests for:
  - Scan screen Start/Stop button behavior (camera unavailable in this
    test environment, so this verifies the button-state machine, not
    actual video capture)
  - Player detail screen: Record Cash Payment button wiring
  - Player detail screen: Export QR button (file copy via QFileDialog)
"""

import os
import sys
from datetime import date

sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))
os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PyQt6.QtWidgets import QApplication, QMessageBox, QFileDialog

QMessageBox.warning = staticmethod(lambda *a, **k: None)
QMessageBox.information = staticmethod(lambda *a, **k: None)
QMessageBox.critical = staticmethod(lambda *a, **k: None)
QMessageBox.question = staticmethod(lambda *a, **k: QMessageBox.StandardButton.Yes)

import db.database as database

TEST_DB_PATH = os.path.join(os.path.dirname(__file__), "_test_scan_controls.db")
database.DB_PATH = TEST_DB_PATH

from models.player import Player, create_player, get_player_by_id
from models.subscription import activate_subscription, suspend_subscription, get_active_subscription
from ui.scan_screen import ScanScreen
from ui.player_detail_screen import PlayerDetailScreen
from ui.update_payment_dialog import UpdatePaymentDialog

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


def make_player(name="Scan Control Player"):
    unique_id = f"299{os.urandom(5).hex()}"[:14]
    p = Player(None, name, unique_id, "01001112222", "2013-01-01", None, "small", None)
    return create_player(p)


# ---------- Scan screen Start/Stop ----------

def test_scan_screen_starts_with_camera_off():
    get_app()
    screen = ScanScreen()
    assert screen.stop_scan_button.isEnabled() is False
    assert screen.start_scan_button.isEnabled() is True
    assert "off" in screen.camera_status_label.text().lower()


def test_start_scan_with_no_camera_available_shows_unavailable_state():
    get_app()
    screen = ScanScreen()
    # This container has no webcam, so this exercises the real "camera
    # failed to open" branch of start_camera() exactly as a machine
    # without a webcam attached would hit it.
    screen._on_start_scan_clicked()

    assert "unavailable" in screen.camera_label.text().lower()
    assert "unavailable" in screen.camera_status_label.text().lower()
    # Since the camera never actually started, Stop should NOT have been
    # enabled — only a successfully opened camera should enable it.
    assert screen.stop_scan_button.isEnabled() is False


def test_stop_scan_resets_ui_state():
    get_app()
    screen = ScanScreen()
    # Manually simulate "was scanning" state to test the stop handler in
    # isolation from whether a real camera could open here.
    screen.start_scan_button.setEnabled(False)
    screen.stop_scan_button.setEnabled(True)
    screen.camera_status_label.setText("Scanning…")

    screen._on_stop_scan_clicked()

    assert screen.start_scan_button.isEnabled() is True
    assert screen.stop_scan_button.isEnabled() is False
    assert "off" in screen.camera_status_label.text().lower()


# ---------- Record Cash Payment ----------

def test_record_payment_button_disabled_with_no_subscription():
    get_app()
    pid = make_player()
    detail = PlayerDetailScreen(pid)
    assert detail.record_payment_button.isEnabled() is False


def test_record_payment_reactivates_and_refreshes_detail_screen(monkeypatch):
    get_app()
    pid = make_player()
    sub_id = activate_subscription(pid, "8", date.today(), "reception", 250.0, date.today())
    suspend_subscription(sub_id)

    detail = PlayerDetailScreen(pid)
    assert "SUSPENDED" in detail.sub_status_label.text()
    assert detail.record_payment_button.isEnabled() is True

    def fake_exec(self):
        self.amount_input.setValue(250.0)
        return True

    monkeypatch.setattr(UpdatePaymentDialog, "exec", fake_exec)
    monkeypatch.setattr(UpdatePaymentDialog, "get_values", lambda self: (250.0, date.today()))

    detail._on_record_payment()

    assert "ACTIVE" in detail.sub_status_label.text()


# ---------- Export QR ----------

def test_export_qr_copies_file_to_chosen_destination(monkeypatch, tmp_path):
    get_app()
    pid = make_player()
    from logic.qr_utils import generate_qr_for_player
    from models.player import update_player

    qr_path = generate_qr_for_player(pid)
    player = get_player_by_id(pid)
    player.qr_code_path = qr_path
    update_player(player)

    detail = PlayerDetailScreen(pid)

    dest = str(tmp_path / "exported_qr.png")
    monkeypatch.setattr(QFileDialog, "getSaveFileName", staticmethod(lambda *a, **k: (dest, "")))

    detail._on_export_qr()

    assert os.path.exists(dest)


def test_export_qr_with_no_code_shows_message(monkeypatch):
    get_app()
    pid = make_player()  # never had a QR generated
    detail = PlayerDetailScreen(pid)

    called = {"shown": False}
    monkeypatch.setattr(
        QMessageBox, "information",
        staticmethod(lambda *a, **k: called.__setitem__("shown", True)),
    )

    detail._on_export_qr()
    assert called["shown"] is True
