"""
Regression test for the "camera opens but never scans" bug.

Every other scan_screen test calls handle_player_id() directly, which
bypasses the camera-to-handler wiring entirely — that's exactly how the
real bug (decode_qr_from_frame's return value being re-checked for a
prefix it no longer had) went unnoticed through every previous test pass.
This test drives _poll_camera() itself, feeding it a real frame containing
a real generated QR code, with only cv2.VideoCapture mocked out (no camera
hardware needed) — so it exercises the exact same code path a live camera
would.
"""

import os
import sys
from datetime import date
from unittest.mock import MagicMock

sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))
os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PyQt6.QtWidgets import QApplication, QMessageBox

QMessageBox.warning = staticmethod(lambda *a, **k: None)

import cv2
import db.database as database

TEST_DB_PATH = os.path.join(os.path.dirname(__file__), "_test_camera_pipeline.db")
database.DB_PATH = TEST_DB_PATH

from models.player import Player, create_player
from models.subscription import activate_subscription
from models.attendance import get_attendance_for_player
from logic.qr_utils import generate_qr_for_player
from ui.scan_screen import ScanScreen

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


def test_poll_camera_actually_checks_in_a_scanned_qr(monkeypatch):
    """
    This is the exact regression test for the reported bug: generate a
    REAL QR image for a REAL player, load it as a frame (exactly as
    cv2.VideoCapture.read() would hand one to _poll_camera), and confirm
    the full pipeline — decode -> parse -> handle_player_id -> log
    attendance — actually fires. Before the fix, this test fails because
    _poll_camera's startswith("PLAYER:") check silently swallowed every
    decoded payload.
    """
    get_app()

    p = Player(None, "Camera Pipeline Player", "29901010199988", "01000000000",
               "2013-01-01", None, "small", None)
    pid = create_player(p)
    qr_path = generate_qr_for_player(pid)

    activate_subscription(pid, "12", date.today(), "reception", 300.0, date.today())

    import logic.validation as validation
    original = validation.validate_check_in
    from datetime import date as date_cls

    def forced(player_id, today):
        return original(player_id, date_cls(2026, 9, 16))  # a Wednesday

    monkeypatch.setattr("ui.checkin_service.validate_check_in", forced)

    screen = ScanScreen()

    # Load the real generated QR image as the "camera frame".
    frame = cv2.imread(qr_path)
    assert frame is not None, "test setup problem: QR image failed to load"

    # Mock only the camera hardware — everything else is the real pipeline.
    fake_cap = MagicMock()
    fake_cap.read.return_value = (True, frame)
    screen._cap = fake_cap

    screen._poll_camera()

    history = get_attendance_for_player(pid)
    assert len(history) == 1, (
        "handle_player_id was never called — the camera-to-handler wiring "
        "is broken (this is the exact bug this test guards against)"
    )
    assert history[0].result == "allowed"


def test_poll_camera_ignores_frame_with_no_qr_code():
    get_app()
    screen = ScanScreen()

    import numpy as np
    blank_frame = np.zeros((480, 640, 3), dtype="uint8")

    fake_cap = MagicMock()
    fake_cap.read.return_value = (True, blank_frame)
    screen._cap = fake_cap

    # Should not raise, and should not attempt any check-in.
    screen._poll_camera()
    # No assertion needed beyond "didn't crash" — there's no player to
    # look up from a blank frame, so nothing should have been logged.
