"""
Recalculates the DERIVED fields (eligibility_flag, score, priority_tier,
level_tier, location_bucket, completeness_pct, missing_fields, status) for
every existing player row, using the current logic.py rules.

Why this exists: logic.py's eligibility rules can change over time (e.g.
the years_resident_in_italy fix shipped alongside this script -- see
README/project notes). Fixing the code only affects *new* submissions;
anyone already in the database keeps whatever was computed at the time
they applied. This script re-runs evaluate_player() against each row's
already-stored raw answers and updates just the derived columns to match
current logic -- it never touches what an applicant actually typed in
(full_name, email, holds_italian_passport, etc. are all left alone).

It also respects staff overrides: compute_status() never overwrites a
status a staff member has already set (Contacted/Shortlisted/Rejected/
Closed/Stale), same as it does for a live submission -- recomputing scores
won't un-close a closed case or move a shortlisted player back to New.

Usage (from your own machine, same DATABASE_URL as seed.py etc.):
    # Preview only -- shows what would change, writes nothing:
    DATABASE_URL="postgresql://..." python3 recompute_scores.py

    # Actually apply the changes:
    DATABASE_URL="postgresql://..." python3 recompute_scores.py --apply
"""
import os
import sys

try:
    import psycopg2
    import psycopg2.extras
except ImportError:
    sys.exit("Missing dependency. Run: pip3 install psycopg2-binary")

import logic

DERIVED_COLS = [
    "completeness_pct", "missing_fields", "level_tier", "location_bucket",
    "eligibility_flag", "eligibility_flag_auto", "score", "priority_tier", "status",
]
# Deliberately NOT touched here: eligibility_flag_override,
# eligibility_overridden_by, eligibility_overridden_at -- those are a staff
# decision (see app.py's override_eligibility()) and evaluate_player()
# already reads eligibility_flag_override off each row to fold it back into
# the recomputed eligibility_flag, so overrides survive a recompute intact.

url = os.environ.get("DATABASE_URL")
if not url:
    sys.exit("Set DATABASE_URL first, e.g.:\n  DATABASE_URL=\"postgresql://...\" python3 recompute_scores.py")

apply_changes = "--apply" in sys.argv

conn = psycopg2.connect(url)
cur = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
cur.execute("SELECT * FROM players ORDER BY id")
rows = cur.fetchall()

changed = []
for row in rows:
    player = dict(row)
    new_fields = logic.evaluate_player(player)
    diffs = {k: (player.get(k), v) for k, v in new_fields.items() if str(player.get(k)) != str(v)}
    if diffs:
        changed.append((row["id"], row["full_name"], row["email"], diffs, new_fields))

if not changed:
    print(f"Checked {len(rows)} players. Nothing to update -- all derived fields already match current logic.")
else:
    print(f"Checked {len(rows)} players. {len(changed)} need updating:\n")
    for player_id, name, email, diffs, _ in changed:
        print(f"  #{player_id} {name} <{email}>")
        for field, (old, new) in diffs.items():
            print(f"      {field}: {old!r} -> {new!r}")
        print()

    if apply_changes:
        update_cur = conn.cursor()
        for player_id, _, _, _, new_fields in changed:
            set_clause = ", ".join(f"{c} = %s" for c in DERIVED_COLS)
            update_cur.execute(
                f"UPDATE players SET {set_clause} WHERE id = %s",
                [new_fields[c] for c in DERIVED_COLS] + [player_id],
            )
        conn.commit()
        print(f"Applied. Updated {len(changed)} player(s).")
    else:
        print("This was a PREVIEW -- nothing was written. Re-run with --apply to save these changes.")

cur.close()
conn.close()
