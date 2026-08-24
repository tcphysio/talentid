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
import secrets
from functools import wraps
from urllib.parse import urlparse

from flask import Flask, render_template, request, redirect, url_for, flash, Response, session, abort
from datetime import datetime, timedelta
from werkzeug.security import check_password_hash, generate_password_hash

from db import get_conn, init_db
import logic
from translations import translate

app = Flask(__name__)

# RENDER is set automatically to "true" by Render on every service (see
# render.com/docs/environment-variables); DATABASE_URL is the same signal
# Replit uses. Either one means this is a real deployment, not someone's
# local `python app.py` -- and a real deployment must never fall back to
# the hardcoded dev key, because anyone who knows it could forge a session
# cookie claiming to be a logged-in admin (is_staff_admin=True) with zero
# other access. PythonAnywhere isn't covered by this check (no reliable
# runtime signal), so its README section still spells out setting
# SECRET_KEY by hand -- this is defense-in-depth for the other two paths,
# not a replacement for setting it everywhere.
_looks_like_real_deployment = os.environ.get("RENDER") == "true" or bool(os.environ.get("DATABASE_URL"))
_secret_key = os.environ.get("SECRET_KEY")
if not _secret_key:
    if _looks_like_real_deployment:
        raise RuntimeError(
            "SECRET_KEY is not set. Refusing to start in what looks like a real "
            "deployment (RENDER or DATABASE_URL is set) without it -- sessions, "
            "including staff logins, would be forgeable by anyone who knows the "
            "fallback dev key. Set SECRET_KEY in your deployment's environment "
            "variables (render.yaml/render-free.yaml already auto-generate one "
            "for new deployments via a Blueprint)."
        )
    _secret_key = "dev-only-change-me"  # fine for local `python app.py` testing only
app.secret_key = _secret_key

# Cookies are marked Secure (HTTPS-only) automatically in the same real
# deployments detected above. Local `python app.py` testing over plain
# http://127.0.0.1 is the one case this should stay off -- a real browser
# won't store or send a Secure cookie over plain HTTP, which would silently
# break local login testing. For other hosts serving over HTTPS
# (PythonAnywhere, Replit) that aren't auto-detected, set
# FORCE_SECURE_COOKIES=1 to get the same hardening explicitly.
_secure_cookies = _looks_like_real_deployment or os.environ.get("FORCE_SECURE_COOKIES", "").lower() in ("1", "true", "yes")
app.config.update(
    SESSION_COOKIE_SECURE=_secure_cookies,
    SESSION_COOKIE_HTTPONLY=True,
    SESSION_COOKIE_SAMESITE="Lax",
)

SUPPORTED_LANGUAGES = ("en", "it")


CONTACT_EMAIL = os.environ.get("CONTACT_EMAIL", "info@example.org")  # shown on the disclaimer page -- set a real FCRI address in your deployment env


@app.context_processor
def inject_lang():
    return dict(lang=session.get("lang", "en"), contact_email=CONTACT_EMAIL)


@app.template_global("t")
def t(key):
    return translate(key, session.get("lang", "en"))


@app.template_global("csrf_token")
def csrf_token():
    """Per-session anti-CSRF token, generated on first use and reused for
    the rest of the session. Every POST form under /admin embeds this via
    <input type="hidden" name="csrf_token" ...>; _csrf_protect() below
    checks it on submission. Without this, a page on another site could
    auto-submit a hidden form to e.g. /admin/staff/<id>/toggle and, if a
    staff member happened to have an active session, deactivate their
    account with no interaction beyond loading that page."""
    token = session.get("csrf_token")
    if not token:
        token = secrets.token_hex(16)
        session["csrf_token"] = token
    return token


@app.before_request
def _csrf_protect():
    # Scoped to /admin rather than every POST: /apply is a public form with
    # no session-based privilege to abuse (anyone can already submit it,
    # logged in or not), so a CSRF token there wouldn't protect anything a
    # visitor doesn't already have access to. Every /admin POST, though,
    # acts on behalf of whichever staff session is attached to the request.
    if request.method == "POST" and request.path.startswith("/admin"):
        expected = session.get("csrf_token", "")
        submitted = request.form.get("csrf_token", "")
        if not expected or not secrets.compare_digest(submitted, expected):
            abort(400, description="Your session expired or this form came from an untrusted source. Please refresh the page and try again.")


@app.after_request
def _security_headers(response):
    response.headers.setdefault("X-Content-Type-Options", "nosniff")
    response.headers.setdefault("X-Frame-Options", "DENY")
    response.headers.setdefault("Referrer-Policy", "strict-origin-when-cross-origin")
    return response


@app.route("/lang/<lang_code>")
def set_language(lang_code):
    if lang_code in SUPPORTED_LANGUAGES:
        session["lang"] = lang_code
    # Send them back to wherever they were, falling back to the intake form.
    # request.referrer reflects the visitor's browser, not something this
    # app controls -- a page on another site could link straight to
    # /lang/it, and blindly redirecting to whatever sent them here would
    # send the visitor wherever that link's page said, i.e. an open
    # redirect. Only follow it when it actually points back at this site.
    referrer = request.referrer
    if referrer and urlparse(referrer).netloc == urlparse(request.host_url).netloc:
        return redirect(referrer)
    return redirect(url_for("apply"))

# Initialise the database on import (not just when run via `python app.py`),
# so this also works under gunicorn/production servers that import the
# module directly instead of running the __main__ block. Safe to call
# repeatedly -- init_db() only builds the schema if the DB file is missing.
init_db()

def login_required(view):
    """
    Gate every /admin route behind a real per-staff session login (see
    /admin/login below) instead of one shared HTTP Basic Auth password.
    This is what makes "who did what" attribution possible -- actions and
    follow-up sweeps get tagged with session["staff_id"], not a free-text
    name anyone could type.
    """
    @wraps(view)
    def wrapped(*args, **kwargs):
        if not session.get("staff_id"):
            return redirect(url_for("login", next=request.path))
        return view(*args, **kwargs)
    return wrapped


def admin_required(view):
    """
    Stricter than login_required -- for staff-management routes only
    (add/deactivate/promote accounts). Regular staff can use the CRM
    (view players, take actions, run follow-ups) but can't touch other
    people's accounts; only accounts with is_admin=True can.
    """
    @wraps(view)
    def wrapped(*args, **kwargs):
        if not session.get("staff_id"):
            return redirect(url_for("login", next=request.path))
        if not session.get("is_staff_admin"):
            flash("Only admin accounts can manage staff.", "error")
            return redirect(url_for("admin"))
        return view(*args, **kwargs)
    return wrapped


FORM_FIELDS = [
    "full_name", "email", "phone", "date_of_birth", "country_of_residence", "city",
    "primary_role", "batting_style", "bowling_style", "current_club", "current_league",
    "highest_level_played", "years_playing", "representative_honours",
    "scorecard_links", "video_links", "referee_name", "referee_contact",
    "birthplace_country", "holds_italian_passport", "italian_parent_or_grandparent",
    "years_resident_in_italy", "current_citizenship", "aire_number", "codice_fiscale", "visa_status",
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

        # Record that *this browser* legitimately created this player_id,
        # so the /thanks page below can't be browsed by anyone who just
        # increments the number in the URL (player_id is a small sequential
        # int -- without this, /thanks/1, /thanks/2, ... would let a
        # stranger enumerate every applicant's name with no login at all).
        # A list, not a single value, because a club/coach/federation
        # nominator can legitimately submit more than one player from the
        # same browser session.
        session.setdefault("own_player_ids", []).append(player_id)

        return redirect(url_for("thanks", player_id=player_id))

    return render_template("apply.html")


@app.route("/disclaimer")
def disclaimer():
    return render_template("disclaimer.html")


@app.route("/thanks/<int:player_id>")
def thanks(player_id):
    if player_id not in session.get("own_player_ids", []):
        abort(404)
    conn = get_conn()
    player = conn.execute("SELECT * FROM players WHERE id = ?", (player_id,)).fetchone()
    conn.close()
    if player is None:
        abort(404)
    return render_template("thanks.html", player=player)


LOGIN_MAX_ATTEMPTS = 5  # wrong passwords in a row before a lockout
LOGIN_LOCKOUT_MINUTES = 15


@app.route("/admin/login", methods=["GET", "POST"])
def login():
    conn = get_conn()
    no_staff_configured = conn.execute("SELECT COUNT(*) AS n FROM staff").fetchone()["n"] == 0

    if request.method == "POST":
        username = request.form.get("username", "").strip()
        password = request.form.get("password", "")
        staff = conn.execute("SELECT * FROM staff WHERE username = ?", (username,)).fetchone()
        now = datetime.now()

        # Brute-force protection: an account with too many wrong passwords
        # in a row is locked out for a while, independent of whether this
        # particular attempt would otherwise have succeeded (so a correct
        # password submitted mid-lockout still doesn't let someone in --
        # otherwise a password guessed on, say, the 6th try after 5
        # lockout-triggering failures would work anyway, defeating the
        # point).
        locked = False
        if staff and staff["locked_until"]:
            try:
                locked = datetime.fromisoformat(staff["locked_until"]) > now
            except ValueError:
                locked = False

        if locked:
            conn.close()
            flash(
                "Too many failed login attempts. Try again in a few minutes, "
                "or contact another admin if you're locked out.",
                "error",
            )
            return render_template("login.html", no_staff_configured=no_staff_configured)

        if staff and staff["is_active"] and check_password_hash(staff["password_hash"], password):
            session["staff_id"] = staff["id"]
            session["staff_username"] = staff["username"]
            session["staff_display_name"] = staff["display_name"] or staff["username"]
            session["is_staff_admin"] = bool(staff["is_admin"])
            conn.execute(
                "UPDATE staff SET last_login_at = ?, failed_login_attempts = 0, locked_until = NULL WHERE id = ?",
                (now.isoformat(), staff["id"]),
            )
            conn.execute("INSERT INTO staff_logins (staff_id) VALUES (?)", (staff["id"],))
            conn.commit()
            conn.close()

            # Only ever redirect back into /admin -- request.args is
            # visitor-controlled, so without this check "next" could be
            # turned into an open redirect to an attacker's site.
            next_url = request.args.get("next", "")
            if not next_url.startswith("/admin"):
                next_url = url_for("admin")
            return redirect(next_url)

        if staff:
            attempts = (staff["failed_login_attempts"] or 0) + 1
            lock_until = None
            if attempts >= LOGIN_MAX_ATTEMPTS:
                lock_until = (now + timedelta(minutes=LOGIN_LOCKOUT_MINUTES)).isoformat()
            conn.execute(
                "UPDATE staff SET failed_login_attempts = ?, locked_until = ? WHERE id = ?",
                (attempts, lock_until, staff["id"]),
            )
            conn.commit()
        conn.close()
        flash("Incorrect username or password.", "error")
        return render_template("login.html", no_staff_configured=no_staff_configured)

    conn.close()
    return render_template("login.html", no_staff_configured=no_staff_configured)


@app.route("/admin/logout")
def logout():
    session.pop("staff_id", None)
    session.pop("staff_username", None)
    session.pop("staff_display_name", None)
    session.pop("is_staff_admin", None)
    return redirect(url_for("login"))


@app.route("/admin/staff", methods=["GET", "POST"])
@admin_required
def staff_list():
    conn = get_conn()

    if request.method == "POST":
        username = request.form.get("username", "").strip()
        display_name = request.form.get("display_name", "").strip()
        password = request.form.get("password", "")
        is_admin = bool(request.form.get("is_admin"))

        if not username or not password:
            flash("Username and password are both required.", "error")
        elif len(password) < 8:
            flash("Password must be at least 8 characters.", "error")
        elif conn.execute("SELECT id FROM staff WHERE username = ?", (username,)).fetchone():
            flash(f"Username '{username}' is already taken.", "error")
        else:
            conn.execute(
                "INSERT INTO staff (username, display_name, password_hash, is_active, is_admin) "
                "VALUES (?, ?, ?, ?, ?)",
                (username, display_name or username, generate_password_hash(password), True, is_admin),
            )
            conn.commit()
            flash(f"Added staff account: {username}")
        conn.close()
        return redirect(url_for("staff_list"))

    staff_members = conn.execute("SELECT * FROM staff ORDER BY username").fetchall()
    conn.close()
    return render_template("staff.html", staff_members=staff_members)


def _active_count(conn, admins_only=False):
    if admins_only:
        return conn.execute(
            "SELECT COUNT(*) AS n FROM staff WHERE is_active = ? AND is_admin = ?", (True, True)
        ).fetchone()["n"]
    return conn.execute("SELECT COUNT(*) AS n FROM staff WHERE is_active = ?", (True,)).fetchone()["n"]


@app.route("/admin/staff/<int:staff_id>/toggle", methods=["POST"])
@admin_required
def toggle_staff(staff_id):
    conn = get_conn()
    target = conn.execute("SELECT * FROM staff WHERE id = ?", (staff_id,)).fetchone()
    if target is None:
        conn.close()
        abort(404)

    if target["is_active"]:
        # Never allow the last active account to deactivate itself (or be
        # deactivated by someone else) -- that would lock every staff
        # member out of the dashboard with no way back in short of a
        # database edit. Separately, never allow the last active *admin*
        # to be deactivated even if other non-admin staff remain active --
        # otherwise no one left could manage staff at all.
        if _active_count(conn) <= 1:
            conn.close()
            flash("Can't deactivate the only active staff account.", "error")
            return redirect(url_for("staff_list"))
        if target["is_admin"] and _active_count(conn, admins_only=True) <= 1:
            conn.close()
            flash("Can't deactivate the only active admin account.", "error")
            return redirect(url_for("staff_list"))
        conn.execute("UPDATE staff SET is_active = ? WHERE id = ?", (False, staff_id))
        flash(f"Deactivated {target['username']}.")
    else:
        conn.execute("UPDATE staff SET is_active = ? WHERE id = ?", (True, staff_id))
        flash(f"Reactivated {target['username']}.")

    conn.commit()
    conn.close()
    return redirect(url_for("staff_list"))


@app.route("/admin/staff/<int:staff_id>/toggle-admin", methods=["POST"])
@admin_required
def toggle_staff_admin(staff_id):
    """Grant or remove admin rights (the ability to manage staff accounts)
    on an existing account. Doesn't touch is_active."""
    conn = get_conn()
    target = conn.execute("SELECT * FROM staff WHERE id = ?", (staff_id,)).fetchone()
    if target is None:
        conn.close()
        abort(404)

    if target["is_admin"]:
        # Never remove admin rights from the only active admin -- that
        # would leave no one able to grant them back short of a database
        # edit, even if other non-admin staff are still active.
        if target["is_active"] and _active_count(conn, admins_only=True) <= 1:
            conn.close()
            flash("Can't remove admin rights from the only active admin account.", "error")
            return redirect(url_for("staff_list"))
        conn.execute("UPDATE staff SET is_admin = ? WHERE id = ?", (False, staff_id))
        flash(f"Removed admin rights from {target['username']}.")
    else:
        conn.execute("UPDATE staff SET is_admin = ? WHERE id = ?", (True, staff_id))
        flash(f"Granted admin rights to {target['username']}.")

    conn.commit()
    conn.close()
    return redirect(url_for("staff_list"))


@app.route("/admin")
@login_required
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
@login_required
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
@login_required
def player_action(player_id):
    action = request.form.get("action")
    note = request.form.get("note", "")
    # Attribution comes from the authenticated session now, not a free-text
    # form field anyone could type any name into.
    staff_name = session.get("staff_display_name", "Staff")
    staff_id = session.get("staff_id")

    conn = get_conn()
    conn.execute(
        "INSERT INTO review_actions (player_id, action, note, staff_name, staff_id) VALUES (?, ?, ?, ?, ?)",
        (player_id, action, note, staff_name, staff_id),
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


def _run_follow_up_sweep(triggered_by: str = "cron") -> int:
    """
    The actual sweep logic, shared by the manual admin button and the
    token-protected /cron endpoint below. Finds incomplete profiles whose
    next_follow_up_due has passed, logs a reminder, and advances the chase
    sequence. Sending is stubbed: it logs the drafted message rather than
    emailing it (see README - Turning the stub into real automation).
    `triggered_by` records who/what caused the sweep -- a staff username
    for a manual click, or "cron" for the scheduled endpoint -- so the
    follow-up history on each player's page shows where each reminder
    actually came from. Returns the number of reminders logged.
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
            "INSERT INTO follow_ups (player_id, channel, reason, message_preview, sent_status, triggered_by) "
            "VALUES (?, 'email', ?, ?, 'stubbed', ?)",
            (player["id"], f"Missing: {', '.join(missing)}", message, triggered_by),
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
@login_required
def run_follow_ups():
    """Manual trigger for staff -- click the button in /admin."""
    sent = _run_follow_up_sweep(triggered_by=session.get("staff_username", "staff"))
    flash(f"Follow-up sweep complete: {sent} reminder(s) logged.")
    return redirect(url_for("admin"))


@app.route("/cron/run-follow-ups")
def cron_run_follow_ups():
    """
    Machine-triggered version of the same sweep, for an external scheduler
    (Render's free tier has no built-in cron) -- see README, "Scheduling
    follow-ups". Deliberately gated by its own FOLLOWUP_CRON_TOKEN rather
    than a staff login, so a third-party scheduler config never needs to
    hold anyone's staff password. Requires ?token=... to match.
    """
    if not FOLLOWUP_CRON_TOKEN:
        return Response(
            "Follow-up cron endpoint is not configured: set FOLLOWUP_CRON_TOKEN "
            "in your deployment environment to enable it.",
            503,
        )
    if not secrets.compare_digest(request.args.get("token") or "", FOLLOWUP_CRON_TOKEN):
        return Response("Forbidden", 403)

    sent = _run_follow_up_sweep()
    return {"reminders_logged": sent}


if __name__ == "__main__":
    # debug=True would enable Werkzeug's interactive debugger -- effectively
    # remote code execution if this ever ended up reachable on a public
    # host instead of behind gunicorn (which never runs this block at all).
    # Not currently reachable in production (Procfile/render*.yaml use
    # `gunicorn app:app`), but a landmine not worth leaving in regardless.
    debug_mode = os.environ.get("FLASK_DEBUG", "").lower() in ("1", "true", "yes")
    app.run(debug=debug_mode, host="0.0.0.0", port=int(os.environ.get("PORT", 5000)))
