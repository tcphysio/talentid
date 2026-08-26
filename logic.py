"""
Categorisation, scoring, completeness and follow-up logic for the
Cricket Italia talent ID CRM.

All rules live in this one file on purpose — this is the part of the
system Cricket Italia staff will actually want to tune (level tiers,
eligibility rules, scoring weights, chase cadence) without touching
the web app or database code.
"""

import re
from datetime import datetime, timedelta

# ---------------------------------------------------------------------------
# Required fields for a submission to count as "Complete".
# Tune this list first if intake requirements change.
# ---------------------------------------------------------------------------
REQUIRED_FIELDS = [
    "full_name", "email", "date_of_birth", "country_of_residence", "primary_role",
    "current_club", "highest_level_played",
    "birthplace_country", "holds_italian_passport",
]

EVIDENCE_FIELDS = ["scorecard_links", "video_links"]

LEVEL_ORDER = [
    "Recreational/Club",
    "Premier/State",
    "First-Class/List A",
    "International",
]

LEVEL_TIER_MAP = {
    "Recreational/Club": "Entry",
    "Premier/State": "Developing",
    "First-Class/List A": "Competitive",
    "International": "Elite",
}

LEVEL_SCORE = {
    "Recreational/Club": 10,
    "Premier/State": 30,
    "First-Class/List A": 55,
    "International": 80,
}

FOLLOW_UP_CADENCE_DAYS = [3, 7, 14]  # reminder schedule after first submission
MAX_FOLLOW_UPS = len(FOLLOW_UP_CADENCE_DAYS)

# Score threshold at which a *complete* record becomes "Ready for Review"
REVIEW_THRESHOLD = 65


def compute_completeness(player: dict):
    """Return (pct:int, missing:list[str]) for required fields."""
    missing = [f for f in REQUIRED_FIELDS if not (player.get(f) or "").strip()]
    pct = round(100 * (len(REQUIRED_FIELDS) - len(missing)) / len(REQUIRED_FIELDS))
    return pct, missing


def compute_location_bucket(player: dict) -> str:
    residence = (player.get("country_of_residence") or "").strip().lower()
    if residence in ("italy", "italia"):
        return "Italy-based"
    if residence:
        return "Overseas"
    return "Unknown"


def compute_level_tier(player: dict) -> str:
    level = player.get("highest_level_played") or ""
    return LEVEL_TIER_MAP.get(level, "Unknown")


def _parse_years(raw: str):
    """
    Pulls a leading integer out of a free-text "years resident" answer
    (e.g. "10+", "10 years", "about 12") the same way the client-side
    pre-screen gate does with JS's parseInt() in apply.html -- returns
    None if there's no leading number to parse.
    """
    if not raw:
        return None
    m = re.match(r"\s*(-?\d+)", raw)
    return int(m.group(1)) if m else None


def compute_eligibility_flag(player: dict) -> str:
    """
    Deliberately conservative: this system captures raw facts, it does not
    adjudicate Italian citizenship/eligibility rules. Federation staff have
    NOT yet locked in whether eligibility runs on descent (jure sanguinis),
    residency, or both -- so anything short of a confirmed passport in hand
    is routed to manual check rather than auto-approved or auto-rejected.
    Tighten this once the federation confirms the exact eligibility rule.

    years_resident_in_italy is treated as a third possible pathway,
    matching the client-side pre-screen gate in apply.html (which already
    lets 3+ years of residency through as "worth a look" alongside
    passport/descent) -- residency claims route to manual check rather
    than "Not Eligible", never to an automatic yes.
    """
    passport = (player.get("holds_italian_passport") or "").strip().lower()
    descent = (player.get("italian_parent_or_grandparent") or "").strip().lower()
    years_resident = _parse_years(player.get("years_resident_in_italy") or "")

    if passport == "yes":
        return "Confirmed Eligible"
    if passport == "applied":
        return "Likely Eligible"
    if descent == "yes" or passport == "unsure" or descent == "unsure":
        return "Needs Manual Check"
    if years_resident is not None and years_resident >= 3:
        return "Needs Manual Check"
    if passport == "no" and descent == "no":
        return "Not Eligible (as stated)"
    return "Needs Manual Check"


ELIGIBILITY_FLAGS = (
    "Confirmed Eligible", "Likely Eligible", "Needs Manual Check", "Not Eligible (as stated)",
)


def compute_score(player: dict, completeness_pct: int, eligibility_flag: str = None) -> int:
    """
    0-100 composite score. Weights are a starting point, not gospel --
    the highest-leverage tuning knob in this whole system. Adjust once
    real submissions start coming in and staff can see which factors
    actually predict a good follow-up.

    eligibility_flag: pass the already-decided effective flag (which may
    be a staff override -- see evaluate_player()) so the score matches
    what's actually displayed. Omit to have it computed fresh from the
    player's raw answers, same as before.
    """
    level = player.get("highest_level_played") or ""
    level_score = LEVEL_SCORE.get(level, 0)  # up to 80

    eligibility = eligibility_flag if eligibility_flag is not None else compute_eligibility_flag(player)
    eligibility_score = {
        "Confirmed Eligible": 15,
        "Likely Eligible": 10,
        "Needs Manual Check": 5,
        "Not Eligible (as stated)": 0,
    }.get(eligibility, 0)

    evidence_score = 0
    if (player.get("video_links") or "").strip():
        evidence_score += 3
    if (player.get("scorecard_links") or "").strip():
        evidence_score += 2

    completeness_bonus = round(completeness_pct / 100 * 0)  # completeness gates status, not score directly

    total = level_score * 0.7 + eligibility_score + evidence_score + completeness_bonus
    return max(0, min(100, round(total)))


def compute_priority_tier(score: int, completeness_pct: int) -> str:
    if completeness_pct < 100:
        return "Needs More Info"
    if score >= REVIEW_THRESHOLD:
        return "Hot Lead"
    if score >= 35:
        return "Warm"
    return "Low Priority"


def compute_status(completeness_pct: int, score: int, current_status: str) -> str:
    """
    Status is mostly derived, but preserves manual staff decisions
    (Contacted / Shortlisted / Rejected / Closed) once set -- the
    automation should never overwrite a human's call. "Closed" is for
    anything that doesn't need chasing but isn't a straight rejection --
    a duplicate entry, a test/validation submission, a player who's
    withdrawn, someone not being pursued right now but not turned away.
    """
    if current_status in ("Contacted", "Shortlisted", "Rejected", "Closed", "Stale"):
        return current_status
    if completeness_pct < 100:
        return "Incomplete-Chasing"
    if score >= REVIEW_THRESHOLD:
        return "Ready for Review"
    return "Complete"


def next_follow_up_date(follow_up_count: int):
    """Return an ISO date string for the next reminder, or None if the
    chase sequence is exhausted (staff should decide manually from there)."""
    if follow_up_count >= MAX_FOLLOW_UPS:
        return None
    days = FOLLOW_UP_CADENCE_DAYS[follow_up_count]
    return (datetime.now() + timedelta(days=days)).strftime("%Y-%m-%d")


def evaluate_player(player: dict) -> dict:
    """
    Run the full rules pipeline on a player record (dict) and return the
    computed fields to persist. This is the single entry point the app
    should call any time a player record is created or updated.

    Respects a staff eligibility override (player["eligibility_flag_override"])
    the same way compute_status() respects a staff status decision above:
    if staff have set one, it wins over the automatic answer for both the
    displayed eligibility_flag and the score, and survives a re-run of this
    function (e.g. from recompute_scores.py) instead of being silently
    recalculated away. The automatic answer is still tracked separately
    (eligibility_flag_auto) so an override never destroys what the rules
    alone would have said.
    """
    completeness_pct, missing = compute_completeness(player)
    level_tier = compute_level_tier(player)
    location_bucket = compute_location_bucket(player)

    auto_flag = compute_eligibility_flag(player)
    override = (player.get("eligibility_flag_override") or "").strip()
    effective_flag = override if override in ELIGIBILITY_FLAGS else auto_flag

    score = compute_score(player, completeness_pct, eligibility_flag=effective_flag)
    priority_tier = compute_priority_tier(score, completeness_pct)
    status = compute_status(completeness_pct, score, player.get("status") or "New")

    return {
        "completeness_pct": completeness_pct,
        "missing_fields": ",".join(missing),
        "level_tier": level_tier,
        "location_bucket": location_bucket,
        "eligibility_flag": effective_flag,
        "eligibility_flag_auto": auto_flag,
        "score": score,
        "priority_tier": priority_tier,
        "status": status,
    }


def build_follow_up_message(player: dict, missing: list) -> str:
    """
    Draft the reminder message for a missing-info chase. Stubbed in the
    prototype (logged, not sent) -- see README for wiring this to a real
    email provider.
    """
    field_labels = {
        "full_name": "your full name",
        "email": "a contact email",
        "date_of_birth": "your date of birth",
        "country_of_residence": "your country of residence",
        "primary_role": "your playing role (batter/bowler/all-rounder/keeper)",
        "current_club": "your current club",
        "highest_level_played": "the highest level you've played at",
        "birthplace_country": "your country of birth",
        "holds_italian_passport": "whether you hold an Italian passport",
    }
    friendly = [field_labels.get(f, f) for f in missing]
    name = player.get("full_name") or "there"
    items = "; ".join(friendly)
    return (
        f"Hi {name}, thanks for registering interest with Cricket Italia's "
        f"talent ID programme. To move your profile forward we still need: "
        f"{items}. Reply to this email or update your submission when you "
        f"get a chance."
    )
