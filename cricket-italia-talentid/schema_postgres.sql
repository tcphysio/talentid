-- Postgres-flavoured schema for the Replit deployment path.
--
-- Used automatically when the DATABASE_URL env var is set (see db.py) --
-- e.g. Replit's built-in Postgres database. On PythonAnywhere/Render,
-- DATABASE_URL isn't set, so schema.sql (SQLite) is used instead as before.
--
-- Deliberately uses CREATE TABLE IF NOT EXISTS everywhere and never DROPs
-- anything -- init_db() runs on every app start/reload, and this table
-- holds real player submissions, so it must be safe to run repeatedly
-- without ever wiping existing data.

CREATE TABLE IF NOT EXISTS players (
    id SERIAL PRIMARY KEY,

    -- Identity / contact
    full_name TEXT NOT NULL,
    email TEXT NOT NULL,
    phone TEXT,
    date_of_birth TEXT,
    country_of_residence TEXT NOT NULL,
    city TEXT,

    -- Playing profile
    primary_role TEXT,
    batting_style TEXT,
    bowling_style TEXT,
    current_club TEXT,
    current_league TEXT,
    highest_level_played TEXT,
    years_playing TEXT,
    representative_honours TEXT,

    -- Evidence
    scorecard_links TEXT,
    video_links TEXT,
    referee_name TEXT,
    referee_contact TEXT,

    -- Eligibility raw facts
    birthplace_country TEXT,
    holds_italian_passport TEXT,
    italian_parent_or_grandparent TEXT,
    years_resident_in_italy TEXT,
    current_citizenship TEXT,
    visa_status TEXT,

    -- Nomination source
    nominated_by TEXT,
    nominator_name TEXT,
    nominator_contact TEXT,

    -- System-derived fields
    submitted_at TEXT NOT NULL DEFAULT to_char(now(), 'YYYY-MM-DD HH24:MI:SS'),
    last_updated_at TEXT NOT NULL DEFAULT to_char(now(), 'YYYY-MM-DD HH24:MI:SS'),

    completeness_pct INTEGER DEFAULT 0,
    missing_fields TEXT,

    level_tier TEXT,
    location_bucket TEXT,
    eligibility_flag TEXT,

    score INTEGER DEFAULT 0,
    priority_tier TEXT,

    status TEXT DEFAULT 'New',

    follow_up_count INTEGER DEFAULT 0,
    next_follow_up_due TEXT
);

CREATE TABLE IF NOT EXISTS follow_ups (
    id SERIAL PRIMARY KEY,
    player_id INTEGER NOT NULL REFERENCES players(id),
    created_at TEXT NOT NULL DEFAULT to_char(now(), 'YYYY-MM-DD HH24:MI:SS'),
    channel TEXT DEFAULT 'email',
    reason TEXT,
    message_preview TEXT,
    sent_status TEXT DEFAULT 'stubbed'
);

CREATE TABLE IF NOT EXISTS review_actions (
    id SERIAL PRIMARY KEY,
    player_id INTEGER NOT NULL REFERENCES players(id),
    created_at TEXT NOT NULL DEFAULT to_char(now(), 'YYYY-MM-DD HH24:MI:SS'),
    action TEXT NOT NULL,
    note TEXT,
    staff_name TEXT
);
