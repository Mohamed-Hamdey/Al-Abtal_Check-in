"""
Database connection helper.

Local-only storage: a single SQLite file, in the user's LocalAppData
folder on Windows. The schema (.sql) ships inside the app bundle and is
read from there. The database itself is writable user data.
"""

import sqlite3
import os
import sys

sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))
from paths import bundled_path, user_data_path, user_data_root


# Schema: read-only, ships inside the bundle.
SCHEMA_PATH = bundled_path("db", "schema.sql")

# Database: writable, lives outside the bundle so it survives app upgrades.
DB_PATH = user_data_path("academy.db")


def get_connection() -> sqlite3.Connection:
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    return conn


def init_db() -> None:
    """
    Create tables if they don't exist yet.
    Safe to call every time the app starts.
    """
    with open(SCHEMA_PATH, "r", encoding="utf-8") as f:
        schema = f.read()

    conn = get_connection()
    try:
        conn.executescript(schema)
        conn.commit()
    finally:
        conn.close()


if __name__ == "__main__":
    init_db()
    print(f"Database ready at: {DB_PATH}")
    print(f"User data root:    {user_data_root()}")