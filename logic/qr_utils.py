"""
QR code generation and scanning.
"""

import os
import sys
import qrcode
import cv2
from pyzbar.pyzbar import decode as zbar_decode

sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))
from paths import user_data_dir


# QR codes are user data — regenerated on demand, so they live in the
# writable data folder, not inside the app bundle.
QR_CODES_DIR = user_data_dir("assets", "qr_codes")


def generate_qr_for_player(player_id: int) -> str:
    """
    Generates a QR code for the player_id and saves it as a PNG under
    the writable data folder. Returns the saved file path.
    """
    os.makedirs(QR_CODES_DIR, exist_ok=True)
    payload = f"PLAYER:{player_id}"

    img = qrcode.make(payload)
    file_path = os.path.join(QR_CODES_DIR, f"player_{player_id}.png")
    img.save(file_path)
    return file_path


def decode_qr_from_frame(frame) -> str | None:
    """
    Takes a single frame (numpy array) and returns the decoded player_id
    as a string, or None. Converts to grayscale first for reliable
    detection on real webcam frames.
    """
    gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
    decoded_objects = zbar_decode(gray)
    for obj in decoded_objects:
        data = obj.data.decode("utf-8")
        if data.startswith("PLAYER:"):
            return data.split(":", 1)[1]
    return None


def open_camera_and_scan_once(camera_index: int = 0) -> str | None:
    """CLI helper — opens the camera and returns the first player_id found."""
    cap = cv2.VideoCapture(camera_index)
    if not cap.isOpened():
        raise RuntimeError(f"Could not open camera at index {camera_index}")

    try:
        while True:
            ret, frame = cap.read()
            if not ret:
                continue
            player_id = decode_qr_from_frame(frame)
            if player_id:
                return player_id
            cv2.imshow("Scan QR - press 'q' to cancel", frame)
            if cv2.waitKey(1) & 0xFF == ord("q"):
                return None
    finally:
        cap.release()
        cv2.destroyAllWindows()