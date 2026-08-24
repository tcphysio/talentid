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
    aire_number TEXT,
    codice_fiscale TEXT,
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

-- Columns added after the table already existed in production need their
-- own statement -- CREATE TABLE IF NOT EXISTS above is a no-op once the
-- table exists, so a brand-new column in that block alone would silently
-- never reach the live Neon database. ADD COLUMN IF NOT EXISTS (Postgres
-- 9.6+) is safe to run on every app boot: no-op if the column is already
-- there, never touches existing data otherwise.
ALTER TABLE players ADD COLUMN IF NOT EXISTS aire_number TEXT;
ALTER TABLE players ADD COLUMN IF NOT EXISTS codice_fiscale TEXT;

CREATE TABLE IF NOT EXISTS follow_ups (
    id SERIAL PRIMARY KEY,
    player_id INTEGER NOT NULL REFERENCES players(id),
    created_at TEXT NOT NULL DEFAULT to_char(now(), 'YYYY-MM-DD HH24:MI:SS'),
    channel TEXT DEFAULT 'email',
    reason TEXT,
    message_preview TEXT,
    sent_status TEXT DEFAULT 'stubbed'
);

-- Which staff member (or 'cron' for the scheduled sweep) triggered this
-- follow-up. Added after follow_ups already existed in production, so it
-- needs its own ADD COLUMN IF NOT EXISTS like aire_number/codice_fiscale
-- above.
ALTER TABLE follow_ups ADD COLUMN IF NOT EXISTS triggered_by TEXT;

CREATE TABLE IF NOT EXISTS review_actions (
    id SERIAL PRIMARY KEY,
    player_id INTEGER NOT NULL REFERENCES players(id),
    created_at TEXT NOT NULL DEFAULT to_char(now(), 'YYYY-MM-DD HH24:MI:SS'),
    action TEXT NOT NULL,
    note TEXT,
    staff_name TEXT
);

-- Which staff account performed this action -- staff_name (free text) is
-- kept alongside for display/back-compat, but staff_id is the real link
-- to the staff table now that logins are per-person.
ALTER TABLE review_actions ADD COLUMN IF NOT EXISTS staff_id INTEGER;

-- Per-staff login accounts, replacing the old single shared
-- ADMIN_USERNAME/ADMIN_PASSWORD HTTP Basic Auth. See db.py's
-- _bootstrap_staff() -- on first boot after this upgrade, if this table is
-- still empty, one account is auto-created from those same env vars so an
-- existing deployment never gets locked out.
CREATE TABLE IF NOT EXISTS staff (
    id SERIAL PRIMARY KEY,
    username TEXT NOT NULL UNIQUE,
    display_name TEXT,
    password_hash TEXT NOT NULL,
    is_active BOOLEAN NOT NULL DEFAULT true,
    created_at TEXT NOT NULL DEFAULT to_char(now(), 'YYYY-MM-DD HH24:MI:SS'),
    last_login_at TEXT
);

-- Only admin accounts can add/deactivate/promote other staff -- everyone
-- else gets the regular dashboard (view players, take actions, run
-- follow-ups) but not /admin/staff. Added after `staff` already existed
-- in production, so it needs its own ADD COLUMN IF NOT EXISTS like the
-- other post-hoc columns above. The bootstrap account (see db.py's
-- _bootstrap_staff()) is always granted admin so there's never a deployment
-- with zero admins.
ALTER TABLE staff ADD COLUMN IF NOT EXISTS is_admin BOOLEAN NOT NULL DEFAULT false;

-- Brute-force protection on /admin/login: after LOGIN_MAX_ATTEMPTS wrong
-- passwords in a row, the account is locked out until locked_until passes.
-- Reset to 0/NULL on a successful login. Added after `staff` already
-- existed in production, so these need their own ADD COLUMN IF NOT EXISTS
-- too.
ALTER TABLE staff ADD COLUMN IF NOT EXISTS failed_login_attempts INTEGER NOT NULL DEFAULT 0;
ALTER TABLE staff ADD COLUMN IF NOT EXISTS locked_until TEXT;

-- One row per successful login -- the audit trail of "who logged in when".
CREATE TABLE IF NOT EXISTS staff_logins (
    id SERIAL PRIMARY KEY,
    staff_id INTEGER NOT NULL REFERENCES staff(id),
    logged_in_at TEXT NOT NULL DEFAULT to_char(now(), 'YYYY-MM-DD HH24:MI:SS')
);
