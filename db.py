"""
Database layer with two backends:

- SQLite (default) -- used on PythonAnywhere and Render, where the file
  lives in DB_DIR (a local folder, or a mounted persistent disk on Render).
- Postgres -- used automatically when a DATABASE_URL env var is present,
  which is how Replit's built-in Postgres database identifies itself.
  Chosen for Replit specifically because Replit's own docs warn that a
  deployment's local filesystem isn't safe to write real data to, so
  SQLite-on-disk (our approach everywhere else) doesn't work there.

app.py and seed.py are written once, against a sqlite3-shaped API
(conn.execute(sql, params).fetchone()/.fetchall(), row["col"] access,
dict(row)). The _PGConnWrapper below exists so that same code runs
unchanged against Postgres -- it rewrites '?' placeholders to '%s' and
returns dict-like rows via RealDictCursor. If you're debugging a query
that behaves oddly on one backend but not the other, this file is the
first place to look.
"""

import os
import re
from pathlib import Path

from werkzeug.security import generate_password_hash

DATABASE_URL = os.environ.get("DATABASE_URL")  # set automatically by Replit; unset on PythonAnywhere/Render
USE_POSTGRES = bool(DATABASE_URL)

# Same env vars that used to gate the old shared HTTP Basic Auth login.
# Now they're only used once, to bootstrap the very first staff account
# (see _bootstrap_staff below) -- after that, staff manage accounts from
# the /admin/staff page and these env vars are no longer read at request
# time.
ADMIN_USERNAME = os.environ.get("ADMIN_USERNAME", "admin")
ADMIN_PASSWORD = os.environ.get("ADMIN_PASSWORD")

# DB_DIR can be overridden via env var to point at a mounted persistent disk
# (used for Render). Only relevant for the SQLite backend.
DB_DIR = Path(os.environ.get("DB_DIR", Path(__file__).parent / "instance"))
DB_PATH = DB_DIR / "talentid.db"
SCHEMA_PATH_SQLITE = Path(__file__).parent / "schema.sql"
SCHEMA_PATH_PG = Path(__file__).parent / "schema_postgres.sql"

if USE_POSTGRES:
    import psycopg2
    import psycopg2.extras
else:
    import sqlite3

_QMARK_RE = re.compile(r"\?")


class _PGConnWrapper:
    """Makes a psycopg2 connection behave like sqlite3.Connection for the
    specific subset of the API this app uses."""

    def __init__(self, conn):
        self._conn = conn

    def execute(self, sql, params=()):
        sql = _QMARK_RE.sub("%s", sql)
        # The one SQLite-specific idiom in app.py (grab the id of the row
        # just inserted). Postgres's equivalent is lastval() -- the last
        # value drawn from a sequence in the current session, which is
        # exactly what a SERIAL primary key uses under the hood.
        if sql.strip() == "SELECT last_insert_rowid() AS id":
            sql = "SELECT lastval() AS id"
        cursor = self._conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
        cursor.execute(sql, params)
        return cursor  # RealDictCursor rows already support fetchone()/fetchall() + row["col"] + dict(row)

    def executescript(self, sql):
        cursor = self._conn.cursor()
        cursor.execute(sql)
        cursor.close()

    def commit(self):
        self._conn.commit()

    def close(self):
        self._conn.close()


def get_conn():
    if USE_POSTGRES:
        raw = psycopg2.connect(DATABASE_URL)
        return _PGConnWrapper(raw)

    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    return conn


# Columns added to existing tables after some SQLite databases already
# existed locally. schema.sql only runs for a brand-new file (see init_db
# below), so an existing local dev database needs its own migration path
# too -- mirrors the ALTER TABLE ... ADD COLUMN IF NOT EXISTS approach in
# schema_postgres.sql for the live Postgres database. Never drops or
# rewrites anything. Keyed by table name since the staff-login feature
# added columns to review_actions and follow_ups as well as players.
_NEW_COLUMNS = {
    "players": {
        "aire_number": "TEXT",
        "codice_fiscale": "TEXT",
        "confirm_token": "TEXT",
    },
    "review_actions": {
        "staff_id": "INTEGER",
    },
    "follow_ups": {
        "triggered_by": "TEXT",
    },
    "staff": {
        # Only present if a `staff` table already existed before the
        # admin-role/lockout features shipped (i.e. an upgrade from an
        # earlier per-staff-login release, before these existed at all). A
        # brand new `staff` table already gets these columns from
        # _ensure_staff_tables/schema.sql, so this is a no-op there.
        "is_admin": "INTEGER NOT NULL DEFAULT 0",
        "failed_login_attempts": "INTEGER NOT NULL DEFAULT 0",
        "locked_until": "TEXT",
    },
}


def _migrate_sqlite_columns(conn):
    for table, columns in _NEW_COLUMNS.items():
        existing = {row["name"] for row in conn.execute(f"PRAGMA table_info({table})").fetchall()}
        for col, coltype in columns.items():
            if col not in existing:
                conn.execute(f"ALTER TABLE {table} ADD COLUMN {col} {coltype}")


def _ensure_staff_tables(conn):
    """
    Create the staff/staff_logins tables if they're missing, without
    touching anything else. schema.sql (DROP + CREATE) only runs for a
    brand-new SQLite file, so an existing pre-staff-login database needs
    these created out-of-band -- same reasoning as _migrate_sqlite_columns
    above, just for whole tables instead of columns. SQLite supports
    CREATE TABLE IF NOT EXISTS directly, so this is safe to call on every
    boot.
    """
    conn.execute(
        "CREATE TABLE IF NOT EXISTS staff ("
        "id INTEGER PRIMARY KEY AUTOINCREMENT, "
        "username TEXT NOT NULL UNIQUE, "
        "display_name TEXT, "
        "password_hash TEXT NOT NULL, "
        "is_active INTEGER NOT NULL DEFAULT 1, "
        "is_admin INTEGER NOT NULL DEFAULT 0, "
        "failed_login_attempts INTEGER NOT NULL DEFAULT 0, "
        "locked_until TEXT, "
        "created_at TEXT NOT NULL DEFAULT (datetime('now')), "
        "last_login_at TEXT)"
    )
    conn.execute(
        "CREATE TABLE IF NOT EXISTS staff_logins ("
        "id INTEGER PRIMARY KEY AUTOINCREMENT, "
        "staff_id INTEGER NOT NULL REFERENCES staff(id), "
        "logged_in_at TEXT NOT NULL DEFAULT (datetime('now')))"
    )


def _bootstrap_staff(conn):
    """
    Seed exactly one staff account, from the ADMIN_USERNAME/ADMIN_PASSWORD
    env vars, but only if the staff table is currently empty. This is what
    lets an existing deployment upgrade from shared Basic Auth to per-staff
    logins without anyone getting locked out: the first boot after the
    upgrade turns those same credentials into a real login account. Once
    any staff account exists (including ones added later via /admin/staff),
    this never runs again -- it deliberately does not touch ADMIN_PASSWORD
    on every boot, since by then it may not even be set any more.

    Always granted is_admin=True -- it's the account replacing the old
    all-powerful shared login, so it needs to be able to manage other staff
    from the start. Every other account starts as a non-admin unless an
    admin explicitly grants that when adding it (or promotes it later).
    """
    row = conn.execute("SELECT COUNT(*) AS n FROM staff").fetchone()
    if row["n"] > 0:
        return
    if not ADMIN_PASSWORD:
        return
    conn.execute(
        "INSERT INTO staff (username, display_name, password_hash, is_active, is_admin) VALUES (?, ?, ?, ?, ?)",
        (ADMIN_USERNAME, ADMIN_USERNAME, generate_password_hash(ADMIN_PASSWORD), True, True),
    )


def _ensure_at_least_one_admin(conn):
    """
    Self-healing invariant, not a one-off migration step: if any staff
    accounts exist but none of them are admins, promote all of them to
    admin. This is what makes upgrading a deployment that already has a
    staff table safe -- when is_admin is added as a new column, existing
    rows get its default (false/0), which would otherwise leave a
    deployment with real staff accounts and zero admins, locking everyone
    out of /admin/staff with no way back short of a database edit.

    Safe to run on every boot: the app itself never lets the active-admin
    count reach zero through the UI (see the lockout checks in
    toggle_staff/toggle_staff_admin in app.py), so in normal operation
    there's always >=1 admin already and this is a no-op. It only ever
    actually fires once, right after an upgrade.
    """
    total = conn.execute("SELECT COUNT(*) AS n FROM staff").fetchone()["n"]
    if total == 0:
        return
    admins = conn.execute("SELECT COUNT(*) AS n FROM staff WHERE is_admin = ?", (True,)).fetchone()["n"]
    if admins > 0:
        return
    conn.execute("UPDATE staff SET is_admin = ?", (True,))


def init_db(reset: bool = False):
    """
    Ensure the schema exists. Safe to call on every app start/reload.

    On Postgres, this is always non-destructive (schema_postgres.sql only
    ever uses CREATE TABLE IF NOT EXISTS, never DROP) -- `reset` is ignored
    there on purpose, so a stray reset=True can never wipe real production
    data. On SQLite, `reset` (or a missing DB file) runs schema.sql fresh,
    same as before; an existing SQLite file instead goes through
    _migrate_sqlite_columns() to pick up any new columns without a reset.
    Either way, _bootstrap_staff() then seeds the first login account if
    none exists yet.
    """
    if USE_POSTGRES:
        conn = get_conn()
        with open(SCHEMA_PATH_PG) as f:
            conn.executescript(f.read())
        conn.commit()
        _bootstrap_staff(conn)
        _ensure_at_least_one_admin(conn)
        conn.commit()
        conn.close()
        return

    DB_DIR.mkdir(parents=True, exist_ok=True)
    if reset or not DB_PATH.exists():
        conn = get_conn()
        with open(SCHEMA_PATH_SQLITE) as f:
            conn.executescript(f.read())
        conn.commit()
    else:
        conn = get_conn()
        # Table-creation before column-migration: _migrate_sqlite_columns's
        # "staff" entry (is_admin) needs the staff table to already exist,
        # which it might not yet on a database upgrading straight from
        # before per-staff logins existed at all.
        _ensure_staff_tables(conn)
        _migrate_sqlite_columns(conn)
        conn.commit()
    _bootstrap_staff(conn)
    _ensure_at_least_one_admin(conn)
    conn.commit()
    conn.close()
