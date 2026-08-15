# Federazione Cricket Italiana (FCRI) — Talent ID & CRM (working prototype)

A self-service intake site for prospective players (Italy-based and overseas),
paired with a staff CRM that auto-categorises submissions, scores them, chases
incomplete profiles, and surfaces genuine prospects for human review.

This is a **working prototype**, not a production system. It runs on Flask +
SQLite so it's easy to inspect, run locally, and hand to a developer or
no-code platform. It is not deployed anywhere — see Deployment below.

## What's in the box

- `/apply` — public intake form. Sent to players or partner clubs.
- `/admin` — staff dashboard: filter/sort every submission by status, priority
  tier, eligibility flag, location. Click through to a detail view.
- `/admin/player/<id>` — full profile, follow-up history, and staff actions
  (Mark Contacted / Shortlist / Reject).
- `/admin/run-follow-ups` — runs the automated chase logic on demand (in
  production this would run on a schedule — see below).
- `logic.py` — **all the business rules live here.** Level tiers, eligibility
  flags, scoring weights, follow-up cadence. This is the file to edit as
  Federazione Cricket Italiana (FCRI)'s actual criteria firm up.
- `schema.sql` / `schema_postgres.sql` — the data model, in SQLite and
  Postgres flavours. `db.py` picks automatically based on whether
  `DATABASE_URL` is set (see "Deployment — Replit" below).
- `translations.py` — English/Italian text for the public pages. The
  language toggle (top-right of the header) switches between them.
- `seed.py` — five realistic sample submissions covering different tiers,
  locations, and eligibility states, so the dashboard isn't empty on first run.

## Running it locally

```bash
cd cricket-italia-talentid
pip install -r requirements.txt
python seed.py     # creates instance/talentid.db with 5 sample players
python app.py       # starts on http://127.0.0.1:5000
```

Open `/apply` to submit a test registration, and `/admin` to see it land in
the dashboard.

## How the automation works

**Completeness.** `REQUIRED_FIELDS` in `logic.py` defines what counts as a
complete profile. Anything missing keeps a record in `Incomplete-Chasing`
status.

**Categorisation.**
- *Level tier*: mapped from "highest level played" (Recreational/Club →
  Entry, up to International → Elite).
- *Location bucket*: Italy-based vs Overseas, from country of residence.
- *Eligibility flag*: **deliberately conservative.** The form captures raw
  facts (passport held, Italian parent/grandparent, years resident) but does
  **not** adjudicate Italian citizenship rules — Federazione Cricket Italiana (FCRI) hasn't yet
  confirmed whether eligibility runs on descent (*jure sanguinis*),
  residency, or both. Anything short of a passport already in hand is routed
  to `Needs Manual Check` rather than auto-approved or auto-rejected. Once
  the federation locks in the actual rule, tighten `compute_eligibility_flag()`
  accordingly — that's a five-minute edit once the rule is confirmed.

**Scoring (0–100).** Weighted mostly on playing level, with smaller
contributions from eligibility clarity and evidence provided (video,
scorecards). Weights are a starting point in `compute_score()` — the
highest-value tuning job once real submissions start arriving and staff can
see what actually predicts a good outcome.

**Priority tier.** Incomplete profiles are always `Needs More Info`
regardless of score, so nobody gets scored as a "Low Priority" reject just
because they haven't filled the form in yet. Complete profiles split into
`Hot Lead` (score ≥ 65), `Warm` (≥ 35), or `Low Priority`.

**Status and human override.** Status is computed automatically
(`New` → `Incomplete-Chasing` → `Complete`/`Ready for Review`) *until* a staff
member takes an action (Contacted / Shortlisted / Rejected). From that point
the automation never overwrites the human decision — it's a one-way handoff.

**Follow-up chasing.** Incomplete profiles get reminders on a 3/7/14-day
cadence (`FOLLOW_UP_CADENCE_DAYS`). After three reminders with no update, a
profile is marked `Stale` rather than chased forever. Reminder sending is
**stubbed** in this prototype — the message is drafted and logged to the
`follow_ups` table, not actually emailed. See below for wiring it up.

## Turning the stub into real automation

Two things need connecting for this to run itself in production:

1. **Scheduled follow-up sweeps.** `/admin/run-follow-ups` still works as a
   manual button for staff, but there's now also a machine-triggered
   version at `/cron/run-follow-ups?token=...` for an external scheduler —
   see "Scheduling follow-ups" below.
2. **Real email sending.** Still stubbed as of this build (not yet wired up
   — a deliberate choice, revisit when ready). `build_follow_up_message()`
   in `logic.py` drafts the message; `app.py`'s `_run_follow_up_sweep()`
   logs it instead of sending it. To wire it up: swap the
   `INSERT INTO follow_ups ...` stub for a call to whatever email service
   Federazione Cricket Italiana (FCRI) uses (Gmail SMTP + an app password
   is the simplest option if FCRI already has a Gmail/Workspace address;
   SendGrid or similar if volume grows), and flip `sent_status` from
   `'stubbed'` to `'sent'`.

## Scheduling follow-ups (external cron)

Render's free tier has no built-in cron (that's a paid add-on there), so
the follow-up sweep needs an external scheduler to hit the app on a timer
instead of a staff member clicking the button in `/admin` every day.

`app.py` exposes `/cron/run-follow-ups?token=...` for exactly this — it's
deliberately **not** behind `ADMIN_PASSWORD`, so a third-party scheduler's
config never has to hold the staff dashboard password. It's gated by its
own `FOLLOWUP_CRON_TOKEN` env var instead, which both `render-free.yaml`
and `render.yaml` now auto-generate a random value for on deploy.

### Steps

1. **Get your token.** Render dashboard → your service → Environment →
   copy the value of `FOLLOWUP_CRON_TOKEN`.
2. **Sign up free** at [cron-job.org](https://cron-job.org) (or any similar
   free URL-pinger — EasyCron, UptimeRobot's monitor-as-cron trick, etc.)
3. **Create a new cron job** pointed at:
   ```
   https://<your-service-name>.onrender.com/cron/run-follow-ups?token=<your-token>
   ```
   Set it to run once a day (any time — the sweep only acts on profiles
   whose `next_follow_up_due` has already passed, so running it more or
   less often just changes how promptly it catches up, not what it does).
4. **Verify it's working**: trigger it manually once from cron-job.org's
   dashboard ("Run now" / "Test run"), then check `/admin` — the flash
   message system doesn't apply here (no browser session), but you'll see
   `follow_up_count` increment and new rows in a player's follow-up history
   on `/admin/player/<id>` if any profiles were due.

This same endpoint works for PythonAnywhere and Replit too, if either of
those ever needs an external scheduler instead of the platform's own.

## Deployment — free AND permanent (Render + Neon) — recommended

**This is the one with no ongoing chores.** Two free services, neither of
which ever expires or needs a manual renewal click:

- **Neon** for the database (Postgres). Their free plan is permanent, not
  a trial, no credit card. Data is never deleted for inactivity — the
  database just pauses compute after idle periods and wakes automatically
  on the next request, at no cost.
- **Render** for hosting the app itself. Free web services spin down after
  15 minutes of no traffic, but — unlike PythonAnywhere — they wake back
  up automatically on the next visit, forever, with no manual action ever
  required. The only cost is the first visitor after a quiet spell waiting
  roughly 30-50 seconds for the page to load.

This works because `db.py` already supports Postgres — set a `DATABASE_URL`
environment variable and it switches over automatically, no code changes
needed (see `schema_postgres.sql`). `render-free.yaml` has this
pre-configured as a Render Blueprint.

### Steps

1. **Create a Neon account** at [neon.com](https://neon.com) — no card
   needed. Create a new project (any name/region is fine).
2. **Get the connection string.** On the project dashboard, find the
   "Connection string" box (usually right on the overview page) and copy
   it — it looks like `postgresql://<user>:<password>@<host>/<dbname>`.
   Keep this somewhere handy, you'll paste it into Render in step 6.
3. **Push this project to a GitHub repo** (skip if you already have one
   from an earlier attempt):
   ```bash
   cd cricket-italia-talentid
   git init && git add . && git commit -m "Initial commit"
   git branch -M main
   git remote add origin https://github.com/<your-username>/<repo-name>.git
   git push -u origin main
   ```
4. **Create a Render account** at [render.com](https://render.com) — no
   card needed — and connect it to your GitHub account when prompted.
5. **New + → Blueprint**, point it at your repo. Render will detect
   `render.yaml` by default — tell it to use `render-free.yaml` instead
   (the blueprint file picker lets you choose, or rename/swap which file
   is called `render.yaml` in your repo if it doesn't offer a picker).
6. **Paste in your Neon connection string** when Render prompts for
   `DATABASE_URL`, and set `ADMIN_PASSWORD` to whatever you want staff to
   log into `/admin` with.
7. **Deploy.** Live at `https://<your-service-name>.onrender.com/apply`
   once the build finishes (a couple of minutes).
8. **Seed or don't seed demo data.** Render's free tier has no Shell tab
   (that's paid-only), so run `seed.py` from your own computer instead,
   pointed at the same Neon database:
   ```bash
   DATABASE_URL="<your-neon-connection-string>" python3 seed.py
   ```
   Before treating the site as live for real players, clear the 5 sample
   players the same way:
   ```bash
   DATABASE_URL="<your-neon-connection-string>" python3 clear_demo_data.py
   ```
   `clear_demo_data.py` only deletes rows matching the exact sample emails
   from `seed.py` — safe to run even if real submissions have already come
   in alongside the demo ones.

That's it — no renewal reminders needed for this one.

## Deployment — free but needs monthly attention (PythonAnywhere)

**This is what's currently live** at your `.pythonanywhere.com` address.
No credit card. The trade-off: free web apps need a manual
"renew" click roughly once a month in the dashboard or the site goes
offline (your data is not deleted, the site just stops being reachable
until you renew). Set a monthly reminder for yourself.

Render and most other free-tier hosts wipe their local filesystem when the
service goes idle, which would silently delete real player submissions —
that's why they're not the default recommendation below. See "Deployment —
paid option (Render)" further down if you'd rather avoid the monthly click
and are OK with ~$7.25/month.

### Steps

1. **Sign up free** at [pythonanywhere.com](https://www.pythonanywhere.com)
   — no card needed. Pick the "Beginner" (free) plan.

2. **Upload the project.** In the PythonAnywhere dashboard, open the
   **Files** tab, upload `cricket-italia-talentid.zip` into your home
   directory, then open a **Bash console** (Consoles tab → Bash) and run:
   ```bash
   unzip cricket-italia-talentid.zip
   cd cricket-italia-talentid
   ```

3. **Create a virtualenv and install dependencies** (same Bash console):
   ```bash
   mkvirtualenv --python=/usr/bin/python3.10 talentid-venv
   pip install -r requirements.txt
   ```
   (gunicorn in `requirements.txt` won't be used here — PythonAnywhere runs
   its own WSGI server — that's fine, it's just unused.)

4. **Create the web app.** Go to the **Web** tab → *Add a new web app* →
   choose *Manual configuration* → pick the Python version matching your
   virtualenv (3.10). When asked, set:
   - **Source code**: `/home/<your-username>/cricket-italia-talentid`
   - **Working directory**: same path
   - **Virtualenv**: `/home/<your-username>/.virtualenvs/talentid-venv`

5. **Edit the WSGI configuration file** — the Web tab has a link to it
   (something like `/var/www/<your-username>_pythonanywhere_com_wsgi.py`).
   Replace its contents with:
   ```python
   import sys, os

   path = '/home/<your-username>/cricket-italia-talentid'
   if path not in sys.path:
       sys.path.append(path)

   os.environ['ADMIN_USERNAME'] = 'admin'
   os.environ['ADMIN_PASSWORD'] = 'choose-a-real-password-here'
   os.environ['SECRET_KEY'] = 'choose-any-long-random-string-here'

   from app import app as application
   ```
   Replace `<your-username>`, the password, and the secret with your own
   values — don't leave the placeholders in place.

6. **(Optional) Static files mapping** — Web tab → Static files → add
   URL `/static/` mapped to
   `/home/<your-username>/cricket-italia-talentid/static/`. Not required
   (Flask serves these itself), just slightly faster if set.

7. **Reload the web app** (green button, top of the Web tab). Your site is
   now live at `https://<your-username>.pythonanywhere.com/apply`, and the
   staff dashboard at `.../admin` (behind the username/password from step 5).

8. **Seed or don't seed demo data.** For a quick look with sample data,
   run `python seed.py` once in the Bash console (with the virtualenv
   active: `workon talentid-venv`). **Before sending the link to real
   players**, delete that demo data first — `rm instance/talentid.db` in
   the Bash console, then Reload the web app — so real submissions never
   mix with the five fake sample players.

9. **Set a monthly reminder** to log in and click "Run until 3 months from
   today" (or whatever the current renewal option says) on the Web tab, or
   the site goes offline until you do.

## Deployment — paid option (Render)

If the monthly renewal click becomes annoying, or you outgrow the free
tier's limits (100 CPU-seconds/day, 512MB disk), Render is the more
"set and forget" option. `Procfile`, `render.yaml`, gunicorn, and env-var
config are already in this repo for it — see the comments in `render.yaml`.
Runs about $7.25/month (Starter plan + 1GB persistent disk; Render's free
tier has the same filesystem-wipe problem as everything else's free tier).

1. Push this project to a GitHub repo:
   ```bash
   git init && git add . && git commit -m "Initial commit"
   git branch -M main
   git remote add origin https://github.com/<your-username>/<repo-name>.git
   git push -u origin main
   ```
2. Create a Render account, connect GitHub.
3. **New + → Blueprint**, point it at your repo — `render.yaml` configures
   everything automatically.
4. Set `ADMIN_PASSWORD` when prompted (kept out of git on purpose).
5. Deploy. Live at `https://<your-service-name>.onrender.com/apply`.

## Deployment — Replit

Replit's own docs warn that a deployment's local filesystem isn't safe for
real data (it can be wiped between deploys, on any plan, including paid
Reserved VM). So unlike PythonAnywhere/Render, this app does **not** use a
local SQLite file here — it uses Replit's built-in Postgres database
instead. `db.py` switches to Postgres automatically whenever a
`DATABASE_URL` environment variable is present, which is how Replit's
database identifies itself; nothing else in the app needs to change.
`schema_postgres.sql` is the Postgres-flavoured version of the schema
(same tables, Postgres syntax) — it's used automatically alongside
`schema.sql`, you don't need to pick one manually.

1. Create a new Repl (or open an existing one) and bring in this project's
   files — either import from a GitHub repo you've pushed this to, or
   upload the contents directly.
2. Open the **Database** tool in the Repl (left sidebar) and create a
   Postgres database if one isn't already attached. Replit sets
   `DATABASE_URL` for you automatically once it exists — you don't need to
   copy/paste a connection string yourself.
3. Set the same three env vars as the other hosts, via the Repl's
   **Secrets** tool (padlock icon in the sidebar) rather than a WSGI file
   this time:
   - `ADMIN_USERNAME` → `admin` (or whatever you prefer)
   - `ADMIN_PASSWORD` → a real password
   - `SECRET_KEY` → any long random string
4. Run `python seed.py` once from the Shell if you want the five sample
   players for a first look — **skip this**, or clear the table
   afterwards, before treating it as the real production database (see the
   note at the top of `seed.py` — reseeding on Postgres adds duplicates
   rather than replacing, since the schema never auto-drops data).
5. Deploy the app (Replit's Deploy button) as a **Reserved VM** deployment
   rather than Autoscale — Autoscale can spin your app down to zero between
   requests, which is a slower first-load experience for a form you're
   handing out to clubs; Reserved VM stays warm.
6. Once live, add a custom domain under the deployment's settings if you
   want something more official-looking than the default `.replit.app`
   address.

This path was verified locally against a real Postgres instance before
shipping — schema creation, seeding, the intake form, admin dashboard,
staff actions, and the follow-up sweep all confirmed working identically
to the SQLite version.

### Still worth doing before sending this to real players (any host)

- ~~Spam/bot protection on `/apply`~~ **Done** — a honeypot field now guards
  the form (`static/style.css` `.hp-field` + the check in `app.py`'s
  `apply()`). Catches basic bots that fill in every field; a determined,
  targeted spammer would still get through, so reCAPTCHA is worth adding
  later if that ever becomes a real problem.
- **Wire up real email sending** for follow-up reminders — still stubbed as
  of this build, deferred by choice for now. See "Turning the stub into
  real automation" above when ready to pick it back up. Note:
  PythonAnywhere's free plan restricts outbound internet to an allowlist of
  sites, so check their current docs on sending email before wiring this up
  there specifically.
- ~~Schedule the follow-up sweep~~ **Endpoint done, external scheduler still
  needs setting up** — `/admin/run-follow-ups` still works as a manual
  button, and there's now a `/cron/run-follow-ups?token=...` endpoint for
  an automated daily sweep. See "Scheduling follow-ups" above to actually
  point a free scheduler at it.

## Open decisions for Federazione Cricket Italiana (FCRI)

- **Exact Italian eligibility rule** (descent vs residency vs both) — needed
  to tighten the eligibility logic from "needs manual check" to something
  more automatic.
- **Scoring weights** — current weights are a reasonable starting guess, not
  validated against real recruitment outcomes.
- **Review threshold** (currently score ≥ 65 for "Ready for Review") — tune
  once staff can see how many submissions land in each tier.
- **Who owns `/admin`** day to day — the dashboard is now password-gated
  (HTTP Basic Auth via `ADMIN_PASSWORD`), but that's one shared login, not
  per-staff accounts. Fine for a small team; worth revisiting if more than a
  couple of people need access with individually revocable logins.
