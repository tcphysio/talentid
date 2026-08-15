"""
Seed sample submissions for demo purposes. Run: python seed.py

Note on Postgres (Replit): init_db(reset=True) is non-destructive there on
purpose (see db.py) -- it never drops the players table, so re-running this
script against a Postgres database adds a second copy of the five sample
players rather than replacing them. On SQLite (PythonAnywhere/Render) it
still wipes and recreates the file fresh each time, as before. If you want
a clean slate on Postgres, delete the rows manually first.
"""

from datetime import datetime, timedelta
from db import get_conn, init_db
import logic

SAMPLES = [
    dict(
        full_name="Marco Bianchi", email="marco.bianchi@example.com", phone="+39 333 1234567",
        date_of_birth="1999-04-12", country_of_residence="Italy", city="Bologna",
        primary_role="All-rounder", batting_style="Right-hand bat", bowling_style="Right-arm medium",
        current_club="Bologna CC", current_league="Serie A1", highest_level_played="Premier/State",
        years_playing="9", representative_honours="Italy U19 squad 2018",
        scorecard_links="https://cric.example/bianchi", video_links="https://youtu.be/example1",
        referee_name="Coach Rossi", referee_contact="rossi@example.com",
        birthplace_country="Italy", holds_italian_passport="Yes",
        italian_parent_or_grandparent="Yes", years_resident_in_italy="27",
        current_citizenship="Italian", visa_status="EU/Italian citizen",
        nominated_by="Self", nominator_name="", nominator_contact="",
    ),
    dict(
        full_name="Jayden Fernando", email="jayden.f@example.com", phone="+61 412 345 678",
        date_of_birth="1997-08-03", country_of_residence="Australia", city="Melbourne",
        primary_role="Bowler", batting_style="Right-hand bat", bowling_style="Right-arm fast",
        current_club="Melbourne Grammarians CC", current_league="Victorian Premier Cricket",
        highest_level_played="First-Class/List A", years_playing="12",
        representative_honours="Victoria 2nd XI, Sri Lanka U19",
        scorecard_links="https://cricinfo.example/fernando", video_links="https://youtu.be/example2, https://youtu.be/example3",
        referee_name="Coach Perera", referee_contact="perera@example.com",
        birthplace_country="Sri Lanka", holds_italian_passport="No",
        italian_parent_or_grandparent="Yes", years_resident_in_italy="0",
        current_citizenship="Sri Lankan, Australian PR", visa_status="Non-EU — visa required",
        nominated_by="Coach", nominator_name="Coach Perera", nominator_contact="perera@example.com",
    ),
    dict(
        full_name="Rahul Mehta", email="rahul.mehta@example.com", phone="",
        date_of_birth="2001-01-20", country_of_residence="India", city="Pune",
        primary_role="Batter", batting_style="Left-hand bat", bowling_style="",
        current_club="Pune Districts CA", current_league="", highest_level_played="",
        years_playing="", representative_honours="",
        scorecard_links="", video_links="",
        referee_name="", referee_contact="",
        birthplace_country="India", holds_italian_passport="Unsure",
        italian_parent_or_grandparent="Unsure", years_resident_in_italy="",
        current_citizenship="Indian", visa_status="",
        nominated_by="Self", nominator_name="", nominator_contact="",
    ),
    dict(
        full_name="Luca Conti", email="luca.conti@example.com", phone="+39 340 9876543",
        date_of_birth="2005-11-02", country_of_residence="Italy", city="Roma",
        primary_role="Wicketkeeper-Batter", batting_style="Right-hand bat", bowling_style="",
        current_club="Roma Capannelle CC", current_league="Serie B", highest_level_played="Recreational/Club",
        years_playing="3", representative_honours="",
        scorecard_links="https://cric.example/conti", video_links="",
        referee_name="", referee_contact="",
        birthplace_country="Italy", holds_italian_passport="Yes",
        italian_parent_or_grandparent="Yes", years_resident_in_italy="20",
        current_citizenship="Italian", visa_status="EU/Italian citizen",
        nominated_by="Club", nominator_name="Roma Capannelle CC", nominator_contact="info@romacc.example",
    ),
    dict(
        full_name="Steve Okafor", email="steve.okafor@example.com", phone="+44 7700 900123",
        date_of_birth="1996-06-15", country_of_residence="England", city="Leicester",
        primary_role="Bowler", batting_style="Right-hand bat", bowling_style="Left-arm fast-medium",
        current_club="Leicester Nomads CC", current_league="Leicestershire Premier League",
        highest_level_played="International", years_playing="15",
        representative_honours="Nigeria national team (ODI/T20I), 2019-2023",
        scorecard_links="https://espncricinfo.example/okafor", video_links="https://youtu.be/example4",
        referee_name="Coach Adeyemi", referee_contact="adeyemi@example.com",
        birthplace_country="Nigeria", holds_italian_passport="Applied",
        italian_parent_or_grandparent="Yes", years_resident_in_italy="0",
        current_citizenship="Nigerian, British", visa_status="Non-EU — visa currently held",
        nominated_by="Federation contact", nominator_name="Cricket Italia scout - UK",
        nominator_contact="scout.uk@cricketitalia.example",
    ),
]


def main():
    init_db(reset=True)
    conn = get_conn()

    for s in SAMPLES:
        computed = logic.evaluate_player(s)
        s.update(computed)
        cols = list(s.keys())
        placeholders = ",".join("?" for _ in cols)
        conn.execute(
            f"INSERT INTO players ({','.join(cols)}) VALUES ({placeholders})",
            [s[c] for c in cols],
        )
        player_id = conn.execute("SELECT last_insert_rowid() AS id").fetchone()["id"]

        # Rahul (incomplete) gets a follow-up already due, to demo the sweep
        if s["full_name"] == "Rahul Mehta":
            past_due = (datetime.now() - timedelta(days=1)).strftime("%Y-%m-%d")
            conn.execute(
                "UPDATE players SET next_follow_up_due = ? WHERE id = ?",
                (past_due, player_id),
            )

    conn.commit()
    conn.close()
    print(f"Seeded {len(SAMPLES)} sample players.")


if __name__ == "__main__":
    main()
