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

DATABASE_URL = os.environ.get("DATABASE_URL")  # set automatically by Replit; unset on PythonAnywhere/Render
USE_POSTGRES = bool(DATABASE_URL)

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


def init_db(reset: bool = False):
    """
    Ensure the schema exists. Safe to call on every app start/reload.

    On Postgres, this is always non-destructive (schema_postgres.sql only
    ever uses CREATE TABLE IF NOT EXISTS, never DROP) -- `reset` is ignored
    there on purpose, so a stray reset=True can never wipe real production
    data. On SQLite, `reset` (or a missing DB file) runs schema.sql fresh,
    same as before.
    """
    if USE_POSTGRES:
        conn = get_conn()
        with open(SCHEMA_PATH_PG) as f:
            conn.executescript(f.read())
        conn.commit()
        conn.close()
        return

    DB_DIR.mkdir(parents=True, exist_ok=True)
    if reset or not DB_PATH.exists():
        conn = get_conn()
        with open(SCHEMA_PATH_SQLITE) as f:
            conn.executescript(f.read())
        conn.commit()
        conn.close()
