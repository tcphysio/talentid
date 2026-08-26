"""
Finds and (optionally) removes duplicate player submissions -- the same
person appearing more than once, most likely from someone resubmitting
after the confirmation-page bug made it look like their first submission
failed (see the "Squad validation bugs round" fix -- the data was almost
always saved the first time).

Duplicates are grouped by email address (case-insensitive, whitespace
trimmed) -- the one field every real applicant provides that identifies
them personally (as opposed to nominator_contact, which can legitimately
repeat across several different players nominated by the same coach/club).

Safety rules, applied automatically:
  - A row a staff member has already acted on (Contacted / Shortlisted /
    Rejected / Closed) is NEVER deleted. If more than one row in a group
    has been acted on, the whole group is left alone and flagged for you
    to sort out by hand -- the script won't guess which decision was the
    "right" one.
  - Otherwise, the most complete submission in the group is kept (highest
    completeness_pct; ties broken by the most recent submission); the
    rest are marked for deletion.
  - Deleting a player also deletes its follow_ups and review_actions rows
    first (required -- the database won't allow deleting a player that
    other rows still reference), but only for rows actually being deleted.

Usage (same DATABASE_URL pattern as seed.py / recompute_scores.py):
    # Preview only -- shows what would happen, deletes nothing:
    DATABASE_URL="postgresql://..." python3 find_duplicates.py

    # Actually delete the extra copies:
    DATABASE_URL="postgresql://..." python3 find_duplicates.py --apply
"""
import os
import sys
from collections import defaultdict

try:
    import psycopg2
    import psycopg2.extras
except ImportError:
    sys.exit("Missing dependency. Run: pip3 install psycopg2-binary")

MANUAL_ACTIONED = {"Contacted", "Shortlisted", "Rejected", "Closed"}

url = os.environ.get("DATABASE_URL")
if not url:
    sys.exit("Set DATABASE_URL first, e.g.:\n  DATABASE_URL=\"postgresql://...\" python3 find_duplicates.py")

apply_changes = "--apply" in sys.argv

conn = psycopg2.connect(url)
cur = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
cur.execute("SELECT * FROM players ORDER BY id")
rows = [dict(r) for r in cur.fetchall()]

groups = defaultdict(list)
for r in rows:
    key = (r["email"] or "").strip().lower()
    if key:
        groups[key].append(r)

dupe_groups = {k: v for k, v in groups.items() if len(v) > 1}

if not dupe_groups:
    print(f"Checked {len(rows)} players. No duplicate email addresses found.")
    cur.close()
    conn.close()
    sys.exit(0)

to_delete = []
manual_review = []

for email, group in dupe_groups.items():
    actioned = [r for r in group if r["status"] in MANUAL_ACTIONED]
    if len(actioned) > 1:
        manual_review.append((email, group))
        continue
    if len(actioned) == 1:
        keep = actioned[0]
    else:
        keep = max(group, key=lambda r: (r["completeness_pct"] or 0, r["submitted_at"] or ""))
    for r in group:
        if r["id"] != keep["id"]:
            to_delete.append((r, keep))

print(f"Checked {len(rows)} players, {len(dupe_groups)} email address(es) appear more than once.\n")

if manual_review:
    print("NEEDS MANUAL REVIEW -- more than one entry already has a staff decision, left alone:")
    for email, group in manual_review:
        print(f"  {email}:")
        for r in group:
            print(f"    #{r['id']} {r['full_name']} - {r['status']} - submitted {r['submitted_at']}")
    print()

if to_delete:
    print("Will keep one entry per person, delete the rest:\n")
    for dead, keep in to_delete:
        print(f"  KEEP   #{keep['id']} {keep['full_name']} <{keep['email']}> "
              f"({keep['completeness_pct']}% complete, {keep['status']}, {keep['submitted_at']})")
        print(f"  DELETE #{dead['id']} {dead['full_name']} <{dead['email']}> "
              f"({dead['completeness_pct']}% complete, {dead['status']}, {dead['submitted_at']})\n")

    if apply_changes:
        del_cur = conn.cursor()
        for dead, _ in to_delete:
            del_cur.execute("DELETE FROM follow_ups WHERE player_id = %s", (dead["id"],))
            del_cur.execute("DELETE FROM review_actions WHERE player_id = %s", (dead["id"],))
            del_cur.execute("DELETE FROM players WHERE id = %s", (dead["id"],))
        conn.commit()
        print(f"Applied. Deleted {len(to_delete)} duplicate player(s).")
    else:
        print("This was a PREVIEW -- nothing was deleted. Re-run with --apply to actually delete these.")
else:
    print("Every duplicate group already has exactly one staff-actioned entry to keep -- nothing to delete.")

cur.close()
conn.close()
