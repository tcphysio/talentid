"""
Categorisation, scoring, completeness and follow-up logic for the
Cricket Italia talent ID CRM.

All rules live in this one file on purpose — this is the part of the
system Cricket Italia staff will actually want to tune (level tiers,
eligibility rules, scoring weights, chase cadence) without touching
the web app or database code.
"""

from datetime import datetime, timedelta

# ---------------------------------------------------------------------------
# Required fields for a submission to count as "Complete".
# Tune this list first if intake requirements change.
# ---------------------------------------------------------------------------
REQUIRED_FIELDS = [
    "full_name", "email", "country_of_residence", "primary_role",
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


def compute_eligibility_flag(player: dict) -> str:
    """
    Deliberately conservative: this system captures raw facts, it does not
    adjudicate Italian citizenship/eligibility rules. Federation staff have
    NOT yet locked in whether eligibility runs on descent (jure sanguinis),
    residency, or both -- so anything short of a confirmed passport in hand
    is routed to manual check rather than auto-approved or auto-rejected.
    Tighten this once the federation confirms the exact eligibility rule.
    """
    passport = (player.get("holds_italian_passport") or "").strip().lower()
    descent = (player.get("italian_parent_or_grandparent") or "").strip().lower()

    if passport == "yes":
        return "Confirmed Eligible"
    if passport == "applied":
        return "Likely Eligible"
    if descent == "yes" or passport == "unsure" or descent == "unsure":
        return "Needs Manual Check"
    if passport == "no" and descent == "no":
        return "Not Eligible (as stated)"
    return "Needs Manual Check"


def compute_score(player: dict, completeness_pct: int) -> int:
    """
    0-100 composite score. Weights are a starting point, not gospel --
    the highest-leverage tuning knob in this whole system. Adjust once
    real submissions start coming in and staff can see which factors
    actually predict a good follow-up.
    """
    level = player.get("highest_level_played") or ""
    level_score = LEVEL_SCORE.get(level, 0)  # up to 80

    eligibility = compute_eligibility_flag(player)
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
    (Contacted / Shortlisted / Rejected) once set -- the automation
    should never overwrite a human's call.
    """
    if current_status in ("Contacted", "Shortlisted", "Rejected", "Stale"):
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
    """
    completeness_pct, missing = compute_completeness(player)
    level_tier = compute_level_tier(player)
    location_bucket = compute_location_bucket(player)
    eligibility_flag = compute_eligibility_flag(player)
    score = compute_score(player, completeness_pct)
    priority_tier = compute_priority_tier(score, completeness_pct)
    status = compute_status(completeness_pct, score, player.get("status") or "New")

    return {
        "completeness_pct": completeness_pct,
        "missing_fields": ",".join(missing),
        "level_tier": level_tier,
        "location_bucket": location_bucket,
        "eligibility_flag": eligibility_flag,
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
