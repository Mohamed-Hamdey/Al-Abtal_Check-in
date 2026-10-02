-- AL-Abtal Kung Fu Academy Membership & Attendance System
-- SQLite schema (local-only storage)

CREATE TABLE IF NOT EXISTS players (
    player_id       INTEGER PRIMARY KEY AUTOINCREMENT,
    full_name       TEXT NOT NULL,
    national_id TEXT UNIQUE,
    phone           TEXT NOT NULL,
    dob             TEXT NOT NULL,              -- ISO date: YYYY-MM-DD
    photo_path      TEXT,                       -- local file path under assets/photos/
    player_group    TEXT NOT NULL,              -- key into config.groups (small/large/last)
    qr_code_path    TEXT,                       -- local file path under assets/qr_codes/
    status          TEXT NOT NULL DEFAULT 'active',  -- active / inactive
    notes           TEXT,
    created_at      TEXT NOT NULL DEFAULT (datetime('now'))
);

CREATE TABLE IF NOT EXISTS subscriptions (
    subscription_id INTEGER PRIMARY KEY AUTOINCREMENT,
    player_id       INTEGER NOT NULL,
    plan_type       TEXT NOT NULL,              -- key into config.plans ("4" / "8" / "12")
    start_date      TEXT NOT NULL,              -- ISO date
    expiry_date     TEXT NOT NULL,              -- ISO date, computed at creation
    sessions_total  INTEGER NOT NULL,
    sessions_remaining INTEGER NOT NULL,
    status          TEXT NOT NULL DEFAULT 'active',  -- active / expired / suspended (lazy-evaluated)
    activated_by    TEXT,
    payment_amount  REAL,
    payment_date    TEXT,
    created_at      TEXT NOT NULL DEFAULT (datetime('now')),
    FOREIGN KEY (player_id) REFERENCES players(player_id)
);

CREATE TABLE IF NOT EXISTS attendance_log (
    log_id          INTEGER PRIMARY KEY AUTOINCREMENT,
    player_id       INTEGER NOT NULL,
    subscription_id INTEGER,
    scan_datetime   TEXT NOT NULL DEFAULT (datetime('now')),
    result          TEXT NOT NULL,              -- allowed / denied
    deny_reason     TEXT,
    was_override    INTEGER NOT NULL DEFAULT 0, -- boolean 0/1
    override_note   TEXT,
    recorded_by     TEXT,
    FOREIGN KEY (player_id) REFERENCES players(player_id),
    FOREIGN KEY (subscription_id) REFERENCES subscriptions(subscription_id)
);

CREATE INDEX IF NOT EXISTS idx_players_national_id ON players(national_id);
CREATE INDEX IF NOT EXISTS idx_subscriptions_player ON subscriptions(player_id);
CREATE INDEX IF NOT EXISTS idx_attendance_player ON attendance_log(player_id);
