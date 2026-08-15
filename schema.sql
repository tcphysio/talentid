-- Cricket Italia Talent Identification & CRM
-- Schema: players (submissions) + follow-up log + review actions

DROP TABLE IF EXISTS players;
DROP TABLE IF EXISTS follow_ups;
DROP TABLE IF EXISTS review_actions;

CREATE TABLE players (
    id INTEGER PRIMARY KEY AUTOINCREMENT,

    -- Identity / contact
    full_name TEXT NOT NULL,
    email TEXT NOT NULL,
    phone TEXT,
    date_of_birth TEXT,
    country_of_residence TEXT NOT NULL,
    city TEXT,

    -- Playing profile
    primary_role TEXT,              -- Batter / Bowler / All-rounder / Wicketkeeper
    batting_style TEXT,
    bowling_style TEXT,
    current_club TEXT,
    current_league TEXT,
    highest_level_played TEXT,      -- Recreational/Club, Premier/State, First-Class/List A, International
    years_playing TEXT,
    representative_honours TEXT,    -- free text: rep teams, age-group honours etc.

    -- Evidence
    scorecard_links TEXT,           -- comma-separated URLs
    video_links TEXT,               -- comma-separated URLs
    referee_name TEXT,
    referee_contact TEXT,

    -- Eligibility raw facts (captured, not adjudicated, by the form)
    birthplace_country TEXT,
    holds_italian_passport TEXT,        -- Yes / No / Applied / Unsure
    italian_parent_or_grandparent TEXT, -- Yes / No / Unsure
    years_resident_in_italy TEXT,
    current_citizenship TEXT,
    visa_status TEXT,                   -- EU/Italian citizen, Non-EU - visa required, Non-EU - visa held, N/A

    -- Nomination source
    nominated_by TEXT,              -- Self / Club / Coach / Federation contact
    nominator_name TEXT,
    nominator_contact TEXT,

    -- System-derived fields
    submitted_at TEXT NOT NULL DEFAULT (datetime('now')),
    last_updated_at TEXT NOT NULL DEFAULT (datetime('now')),

    completeness_pct INTEGER DEFAULT 0,
    missing_fields TEXT,                -- comma-separated list of required-but-missing fields

    level_tier TEXT,                    -- computed: Entry / Developing / Competitive / Elite
    location_bucket TEXT,               -- computed: Italy-based / Overseas
    eligibility_flag TEXT,              -- computed: Confirmed Eligible / Likely Eligible / Needs Manual Check / Not Eligible

    score INTEGER DEFAULT 0,            -- 0-100
    priority_tier TEXT,                 -- Hot Lead / Warm / Needs More Info / Low Priority

    status TEXT DEFAULT 'New',          -- New / Incomplete-Chasing / Complete / Ready for Review / Contacted / Shortlisted / Rejected / Stale

    follow_up_count INTEGER DEFAULT 0,
    next_follow_up_due TEXT
);

CREATE TABLE follow_ups (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    player_id INTEGER NOT NULL REFERENCES players(id),
    created_at TEXT NOT NULL DEFAULT (datetime('now')),
    channel TEXT DEFAULT 'email',
    reason TEXT,             -- what was missing / why this reminder fired
    message_preview TEXT,
    sent_status TEXT DEFAULT 'stubbed'  -- 'stubbed' in prototype; 'sent' once wired to real email
);

CREATE TABLE review_actions (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    player_id INTEGER NOT NULL REFERENCES players(id),
    created_at TEXT NOT NULL DEFAULT (datetime('now')),
    action TEXT NOT NULL,    -- Contacted / Shortlisted / Rejected / Note
    note TEXT,
    staff_name TEXT
);
