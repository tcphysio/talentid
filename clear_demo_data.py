"""
Remove the 5 sample players seed.py creates, without touching anything
else in the database. Run: python clear_demo_data.py

Safe by design: it matches only the exact emails in seed.py's SAMPLES list
(imported directly from seed.py, not hand-copied, so the two files can
never drift apart) rather than wiping the whole players table -- so it
won't delete real applicant data even if real submissions have already
started coming in alongside the demo rows.

Also cleans up each demo player's rows in follow_ups and review_actions
first, since both tables reference players.id and the schema has no
ON DELETE CASCADE.
"""

from db import get_conn, init_db
from seed import SAMPLES

DEMO_EMAILS = [s["email"] for s in SAMPLES]


def main():
    init_db()
    conn = get_conn()

    placeholders = ",".join("?" for _ in DEMO_EMAILS)
    rows = conn.execute(
        f"SELECT id, full_name, email FROM players WHERE email IN ({placeholders})",
        DEMO_EMAILS,
    ).fetchall()

    if not rows:
        print("No demo players found (already clear, or none seeded yet).")
        conn.close()
        return

    ids = [r["id"] for r in rows]
    for player_id in ids:
        conn.execute("DELETE FROM follow_ups WHERE player_id = ?", (player_id,))
        conn.execute("DELETE FROM review_actions WHERE player_id = ?", (player_id,))
    id_placeholders = ",".join("?" for _ in ids)
    conn.execute(f"DELETE FROM players WHERE id IN ({id_placeholders})", ids)

    conn.commit()
    conn.close()

    print(f"Removed {len(rows)} demo player(s):")
    for r in rows:
        print(f"  - {r['full_name']} <{r['email']}>")


if __name__ == "__main__":
    main()
