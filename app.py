"""
Cricket Italia Talent ID & CRM prototype.

Two surfaces:
  /apply   - public intake form players/clubs fill in
  /admin   - staff CRM dashboard (list, filter, detail, review actions)

Run:  python app.py
Then open http://127.0.0.1:5000/apply  and  http://127.0.0.1:5000/admin

See README.md for deployment notes and how to wire real email sending.
"""

import os
from functools import wraps

from flask import Flask, render_template, request, redirect, url_for, flash, Response, session
from datetime import datetime

from db import get_conn, init_db
import logic
from translations import translate

app = Flask(__name__)
app.secret_key = os.environ.get("SECRET_KEY", "dev-only-change-me")

SUPPORTED_LANGUAGES = ("en", "it")


@app.context_processor
def inject_lang():
    return dict(lang=session.get("lang", "en"))


@app.template_global("t")
def t(key):
    return translate(key, session.get("lang", "en"))


@app.route("/lang/<lang_code>")
def set_language(lang_code):
    if lang_code in SUPPORTED_LANGUAGES:
        session["lang"] = lang_code
    # Send them back to wherever they were, falling back to the intake form.
    return redirect(request.referrer or url_for("apply"))

# Initialise the database on import (not just when run via `python app.py`),
# so this also works under gunicorn/production servers that import the
# module directly instead of running the __main__ block. Safe to call
# repeatedly -- init_db() only builds the schema if the DB file is missing.
init_db()

ADMIN_USERNAME = os.environ.get("ADMIN_USERNAME", "admin")
ADMIN_PASSWORD = os.environ.get("ADMIN_PASSWORD")  # required in production, see README


def requires_admin_auth(view):
    """
    Gate every /admin route behind HTTP Basic Auth. ADMIN_PASSWORD must be
    set via environment variable in any real deployment -- if it isn't set,
    admin access is refused outright rather than silently left open, since
    this dashboard shows player eligibility/passport/visa data.
    """
    @wraps(view)
    def wrapped(*args, **kwargs):
        if not ADMIN_PASSWORD:
            return Response(
                "Admin dashboard is not configured: set ADMIN_PASSWORD in your "
                "deployment environment to enable staff access.",
                503,
            )
        auth = request.authorization
        if not auth or auth.username != ADMIN_USERNAME or auth.password != ADMIN_PASSWORD:
            return Response(
                "Authentication required", 401,
                {"WWW-Authenticate": 'Basic realm="Cricket Italia Admin"'},
            )
        return view(*args, **kwargs)
    return wrapped


FORM_FIELDS = [
    "full_name", "email", "phone", "date_of_birth", "country_of_residence", "city",
    "primary_role", "batting_style", "bowling_style", "current_club", "current_league",
    "highest_level_played", "years_playing", "representative_honours",
    "scorecard_links", "video_links", "referee_name", "referee_contact",
    "birthplace_country", "holds_italian_passport", "italian_parent_or_grandparent",
    "years_resident_in_italy", "current_citizenship", "visa_status",
    "nominated_by", "nominator_name", "nominator_contact",
]


@app.route("/")
def home():
    return redirect(url_for("apply"))


@app.route("/apply", methods=["GET", "POST"])
def apply():
    if request.method == "POST":
        # Honeypot: a field real visitors never see or fill in (see
        # templates/apply.html + static/style.css .hp-field). Bots that
        # blindly fill every input trip it. Pretend success without
        # touching the database or tipping the bot off.
        if request.form.get("hp_website", "").strip():
            return redirect(url_for("apply", submitted="1"))

        data = {field: request.form.get(field, "").strip() for field in FORM_FIELDS}

        computed = logic.evaluate_player(data)
        data.update(computed)

        conn = get_conn()
        cols = list(data.keys())
        placeholders = ",".join("?" for _ in cols)
        conn.execute(
            f"INSERT INTO players ({','.join(cols)}) VALUES ({placeholders})",
            [data[c] for c in cols],
        )
        conn.commit()
        player_id = conn.execute("SELECT last_insert_rowid() AS id").fetchone()["id"]

        # Schedule first follow-up if incomplete
        if data["completeness_pct"] < 100:
            due = logic.next_follow_up_date(0)
            conn.execute(
                "UPDATE players SET next_follow_up_due = ? WHERE id = ?",
                (due, player_id),
            )
            conn.commit()

        conn.close()
        return redirect(url_for("thanks", player_id=player_id))

    return render_template("apply.html")


@app.route("/thanks/<int:player_id>")
def thanks(player_id):
    conn = get_conn()
    player = conn.execute("SELECT * FROM players WHERE id = ?", (player_id,)).fetchone()
    conn.close()
    return render_template("thanks.html", player=player)


@app.route("/admin")
@requires_admin_auth
def admin():
    conn = get_conn()

    status_filter = request.args.get("status", "")
    tier_filter = request.args.get("tier", "")
    location_filter = request.args.get("location", "")
    sort = request.args.get("sort", "score_desc")

    query = "SELECT * FROM players WHERE 1=1"
    params = []
    if status_filter:
        query += " AND status = ?"
        params.append(status_filter)
    if tier_filter:
        query += " AND priority_tier = ?"
        params.append(tier_filter)
    if location_filter:
        query += " AND location_bucket = ?"
        params.append(location_filter)

    order_map = {
        "score_desc": "score DESC",
        "score_asc": "score ASC",
        "submitted_desc": "submitted_at DESC",
        "submitted_asc": "submitted_at ASC",
    }
    query += f" ORDER BY {order_map.get(sort, 'score DESC')}"

    players = conn.execute(query, params).fetchall()

    summary = conn.execute(
        "SELECT priority_tier, COUNT(*) as n FROM players GROUP BY priority_tier"
    ).fetchall()
    status_counts = conn.execute(
        "SELECT status, COUNT(*) as n FROM players GROUP BY status"
    ).fetchall()

    conn.close()
    return render_template(
        "admin.html",
        players=players,
        summary=summary,
        status_counts=status_counts,
        status_filter=status_filter,
        tier_filter=tier_filter,
        location_filter=location_filter,
        sort=sort,
    )


@app.route("/admin/player/<int:player_id>")
@requires_admin_auth
def player_detail(player_id):
    conn = get_conn()
    player = conn.execute("SELECT * FROM players WHERE id = ?", (player_id,)).fetchone()
    follow_ups = conn.execute(
        "SELECT * FROM follow_ups WHERE player_id = ? ORDER BY created_at DESC", (player_id,)
    ).fetchall()
    actions = conn.execute(
        "SELECT * FROM review_actions WHERE player_id = ? ORDER BY created_at DESC", (player_id,)
    ).fetchall()
    conn.close()
    missing = (player["missing_fields"] or "").split(",") if player["missing_fields"] else []
    return render_template(
        "player_detail.html", player=player, follow_ups=follow_ups, actions=actions, missing=missing
    )


@app.route("/admin/player/<int:player_id>/action", methods=["POST"])
@requires_admin_auth
def player_action(player_id):
    action = request.form.get("action")
    note = request.form.get("note", "")
    staff_name = request.form.get("staff_name", "Staff")

    conn = get_conn()
    conn.execute(
        "INSERT INTO review_actions (player_id, action, note, staff_name) VALUES (?, ?, ?, ?)",
        (player_id, action, note, staff_name),
    )
    status_map = {"Contacted": "Contacted", "Shortlisted": "Shortlisted", "Rejected": "Rejected"}
    if action in status_map:
        conn.execute(
            "UPDATE players SET status = ?, last_updated_at = ? WHERE id = ?",
            (status_map[action], datetime.now().isoformat(), player_id),
        )
    conn.commit()
    conn.close()
    flash(f"Recorded: {action}")
    return redirect(url_for("player_detail", player_id=player_id))


FOLLOWUP_CRON_TOKEN = os.environ.get("FOLLOWUP_CRON_TOKEN")  # see README - Scheduling follow-ups


def _run_follow_up_sweep() -> int:
    """
    The actual sweep logic, shared by the manual admin button and the
    token-protected /cron endpoint below. Finds incomplete profiles whose
    next_follow_up_due has passed, logs a reminder, and advances the chase
    sequence. Sending is stubbed: it logs the drafted message rather than
    emailing it (see README - Turning the stub into real automation).
    Returns the number of reminders logged.
    """
    conn = get_conn()
    today = datetime.now().strftime("%Y-%m-%d")
    due_players = conn.execute(
        "SELECT * FROM players WHERE status = 'Incomplete-Chasing' "
        "AND next_follow_up_due IS NOT NULL AND next_follow_up_due <= ?",
        (today,),
    ).fetchall()

    sent = 0
    for p in due_players:
        player = dict(p)
        missing = (player["missing_fields"] or "").split(",") if player["missing_fields"] else []
        message = logic.build_follow_up_message(player, missing)

        conn.execute(
            "INSERT INTO follow_ups (player_id, channel, reason, message_preview, sent_status) "
            "VALUES (?, 'email', ?, ?, 'stubbed')",
            (player["id"], f"Missing: {', '.join(missing)}", message),
        )

        new_count = player["follow_up_count"] + 1
        next_due = logic.next_follow_up_date(new_count)
        new_status = "Incomplete-Chasing" if next_due else "Stale"

        conn.execute(
            "UPDATE players SET follow_up_count = ?, next_follow_up_due = ?, status = ?, "
            "last_updated_at = ? WHERE id = ?",
            (new_count, next_due, new_status, datetime.now().isoformat(), player["id"]),
        )
        sent += 1

    conn.commit()
    conn.close()
    return sent


@app.route("/admin/run-follow-ups")
@requires_admin_auth
def run_follow_ups():
    """Manual trigger for staff -- click the button in /admin."""
    sent = _run_follow_up_sweep()
    flash(f"Follow-up sweep complete: {sent} reminder(s) logged.")
    return redirect(url_for("admin"))


@app.route("/cron/run-follow-ups")
def cron_run_follow_ups():
    """
    Machine-triggered version of the same sweep, for an external scheduler
    (Render's free tier has no built-in cron) -- see README, "Scheduling
    follow-ups". Deliberately gated by its own FOLLOWUP_CRON_TOKEN rather
    than ADMIN_PASSWORD, so a third-party scheduler config never needs to
    hold the staff dashboard password. Requires ?token=... to match.
    """
    if not FOLLOWUP_CRON_TOKEN:
        return Response(
            "Follow-up cron endpoint is not configured: set FOLLOWUP_CRON_TOKEN "
            "in your deployment environment to enable it.",
            503,
        )
    if request.args.get("token") != FOLLOWUP_CRON_TOKEN:
        return Response("Forbidden", 403)

    sent = _run_follow_up_sweep()
    return {"reminders_logged": sent}


if __name__ == "__main__":
    app.run(debug=True, host="0.0.0.0", port=int(os.environ.get("PORT", 5000)))
