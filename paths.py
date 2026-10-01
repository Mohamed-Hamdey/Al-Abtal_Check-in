"""
Path resolution for the app — bundled vs user-data.

When running from source (python main.py), everything lives in the project
folder and this module behaves as a thin wrapper.

When running as a PyInstaller-frozen .exe, two categories of paths exist:

  * BUNDLED, read-only — config, translations, logo, schema. These ship
    inside the .exe and are unpacked into a temp folder at runtime. Read
    them from sys._MEIPASS.

  * USER DATA, writable — the SQLite database, generated QR codes, and
    (future) player photos. These must live OUTSIDE the bundle, in the
    user's LocalAppData folder, so they survive app updates and aren't
    wiped when the temp folder is cleaned up.

Usage:
    from paths import bundled_path, user_data_path
    cfg_path   = bundled_path("config", "academy_config.json")
    schema     = bundled_path("db", "schema.sql")
    db_file    = user_data_path("academy.db")
    qr_file    = user_data_path("assets", "qr_codes", "player_1.png")
"""

import os
import sys


# ---------------------------------------------------------------------------
# Bundled resources (read-only, shipped with the app)
# ---------------------------------------------------------------------------

def bundled_path(*parts: str) -> str:
    """
    Return an absolute path to a file that ships WITH the app.

    In a frozen build, files are unpacked under sys._MEIPASS.
    In source mode, they live relative to this file (the project root).
    """
    if hasattr(sys, "_MEIPASS"):
        base = sys._MEIPASS
    else:
        base = os.path.dirname(os.path.abspath(__file__))
    return os.path.join(base, *parts)


def project_root() -> str:
    """Root of the source tree (in source mode) or the temp bundle (frozen).
    Use bundled_path() for actual files — this is for logging/debug only."""
    if hasattr(sys, "_MEIPASS"):
        return sys._MEIPASS
    return os.path.dirname(os.path.abspath(__file__))


# ---------------------------------------------------------------------------
# User data (writable, lives outside the bundle)
# ---------------------------------------------------------------------------

APP_DATA_DIRNAME = "AcademySystem"


def user_data_root() -> str:
    """
    Return the writable data root:
      Windows:  %LOCALAPPDATA%\\AcademySystem\\
      macOS:    ~/Library/Application Support/AcademySystem/
      Linux:    ~/.local/share/AcademySystem/
      Fallback: <project root>/data/  (used if LOCALAPPDATA isn't set)

    Never returns a path inside the frozen bundle.
    """
    # Windows: LocalAppData is the correct place for a database — it's not
    # synced to roaming profiles or OneDrive, which is important for SQLite.
    local_appdata = os.environ.get("LOCALAPPDATA")
    if local_appdata:
        return os.path.join(local_appdata, APP_DATA_DIRNAME)

    # macOS
    if sys.platform == "darwin":
        return os.path.join(
            os.path.expanduser("~"), "Library", "Application Support", APP_DATA_DIRNAME
        )

    # Linux / everything else
    xdg = os.environ.get("XDG_DATA_HOME")
    if xdg:
        return os.path.join(xdg, APP_DATA_DIRNAME)
    home = os.path.expanduser("~")
    if home and home != "~":
        return os.path.join(home, ".local", "share", APP_DATA_DIRNAME)

    # Last resort — a folder next to the exe. Only used if all else fails.
    return os.path.join(project_root(), "data")


def user_data_path(*parts: str, create_parent: bool = True) -> str:
    """
    Absolute path to a writable file under user_data_root().
    If create_parent is True (default), the parent directory is created.
    """
    full = os.path.join(user_data_root(), *parts)
    if create_parent:
        parent = os.path.dirname(full)
        if parent:
            os.makedirs(parent, exist_ok=True)
    return full


def user_data_dir(*parts: str) -> str:
    """Absolute path to a writable directory under user_data_root().
    Creates the directory if it doesn't exist."""
    full = os.path.join(user_data_root(), *parts)
    os.makedirs(full, exist_ok=True)
    return full