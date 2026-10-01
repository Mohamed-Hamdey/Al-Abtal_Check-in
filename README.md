# Academy Membership & Attendance System

A local, offline-first membership and QR-based attendance system, originally built for **AL-Abtal Kung Fu Academy** and designed as a reusable template for other academies/clubs.

Runs entirely on one device. No server, no internet dependency, no cloud storage — all data lives in a local SQLite file.

## Reusing this for a different academy

This is the whole point of the template structure: **you should never need to touch any code** to deploy this for a new academy. Only two things change:

1. **`config/academy_config.json`** — academy name, plan types, session counts, allowed training days, group names/times.
2. **`assets/logo/logo.png`** — replace with the new academy's logo.

Everything in `/models`, `/logic`, and `/ui` reads from the config file rather than hardcoding academy-specific values.

## Project structure

```
academy-system/
├── config/
│   ├── academy_config.json   ← EDIT THIS to reuse for a new academy
│   └── config_loader.py      (reads the config — don't hardcode values elsewhere)
├── assets/
│   ├── logo/                 ← swap logo.png here for a new academy
│   ├── qr_codes/             (generated at runtime, not committed to git)
│   └── photos/                (player photos, not committed to git)
├── db/
│   ├── schema.sql             (table definitions)
│   └── database.py            (connection + init helper)
├── models/
│   ├── player.py
│   ├── subscription.py
│   └── attendance.py
├── logic/
│   ├── validation.py          (core check-in rules — the part that must be correct)
│   └── qr_utils.py            (QR generation + scanning)
├── ui/                        (Phase 2 — receptionist scan screen, built next)
├── tests/
│   └── test_validation.py
├── requirements.txt
└── academy.db                 (created on first run — local only, gitignored)
```

## Setup

```bash
python3 -m venv venv
source venv/bin/activate        # Windows: venv\Scripts\activate
pip install -r requirements.txt

# Initialize the local database
python3 db/database.py
```

## Running tests

```bash
pytest tests/ -v
```

## Status

- [x] Phase 1 — Foundation (data model, validation logic, QR gen/scan)
- [ ] Phase 2 — Receptionist scan/check-in interface
- [ ] Phase 3 — Manual admin tools
- [ ] Phase 4 — Attendance history & progress view
- [ ] Phase 5 — Google Form onboarding import

## Core rules (see full spec for details)

- Subscriptions expire on the 1st of the month following activation, regardless of sessions used.
- Missed sessions are lost — no rollover.
- Renewals always create a new subscription row; history is never overwritten.
- Check-in undo is same-day only.
- Subscription status is lazy-evaluated — corrected at scan/lookup time, no background scheduler needed.
