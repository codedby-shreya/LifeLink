"""
Donor–Recipient matching algorithm.
Scores each donor against a recipient and returns ranked candidates.
"""

from __future__ import annotations
import re
from config.constants import (
    BLOOD_COMPATIBILITY,
    EXACT_BLOOD_MATCH_ORGANS,
    SCORE_WEIGHT_BLOOD,
    SCORE_WEIGHT_LOCATION,
    SCORE_WEIGHT_URGENCY,
    SCORE_WEIGHT_AVAILABILITY,
    URGENCY_WEIGHT,
)


# ── Blood-type scoring ────────────────────────────────────────────────────────

def blood_score(donor_blood: str, recipient_blood: str, organ: str = "") -> tuple[float, str]:
    """
    Returns (score_0_to_1, reason_string).
    For exact-match organs (Heart, Lung …) only identical blood types qualify.
    """
    compatible = BLOOD_COMPATIBILITY.get(recipient_blood, [])

    if organ and organ in EXACT_BLOOD_MATCH_ORGANS:
        if donor_blood == recipient_blood:
            return 1.0, f"Exact blood type match ({donor_blood}) ✅"
        return 0.0, f"Blood type mismatch — {organ} requires exact match ({recipient_blood}), donor is {donor_blood} ❌"

    if donor_blood == recipient_blood:
        return 1.0, f"Exact blood type match ({donor_blood}) ✅"
    if donor_blood in compatible:
        return 0.8, f"Compatible blood type: donor {donor_blood} → recipient {recipient_blood} ✅"
    return 0.0, f"Incompatible blood types: donor {donor_blood}, recipient {recipient_blood} ❌"


# ── Location scoring ──────────────────────────────────────────────────────────

def location_score(donor: dict, recipient: dict) -> tuple[float, str]:
    """
    Simple tier-based scoring:
      Same city   → 1.0
      Same state  → 0.6
      Different   → 0.2
    """
    d_city  = (donor.get("city")  or "").strip().lower()
    r_city  = (recipient.get("city")  or "").strip().lower()
    d_state = (donor.get("state") or "").strip().lower()
    r_state = (recipient.get("state") or "").strip().lower()

    if d_city and r_city and d_city == r_city:
        return 1.0, f"Same city ({donor.get('city')}) 📍"
    if d_state and r_state and d_state == r_state:
        return 0.6, f"Same state ({donor.get('state')}) 📍"
    return 0.2, f"Different state (Donor: {donor.get('state')}, Recipient: {recipient.get('state')}) 📍"


# ── Urgency scoring ───────────────────────────────────────────────────────────

def urgency_score(urgency: str) -> tuple[float, str]:
    max_weight = max(URGENCY_WEIGHT.values())
    weight = URGENCY_WEIGHT.get(urgency, 1)
    return weight / max_weight, f"Urgency: {urgency}"


# ── Organ availability check ──────────────────────────────────────────────────

def organ_available(donor: dict, organ_needed: str) -> bool:
    """Returns True if the donor has registered the required organ."""
    if not organ_needed:
        return True  # blood donation — no organ check
    donor_organs = [o.lower() for o in (donor.get("organs") or [])]
    return organ_needed.lower() in donor_organs


# ── Main matching function ────────────────────────────────────────────────────

def match_donors_to_recipient(recipient: dict, donors: list, top_n: int = 10) -> list[dict]:
    """
    Score every available donor against the recipient and return the top-N matches
    sorted by descending score.

    Each result dict contains:
      donor, recipient, total_score, blood_score, location_score, urgency_score,
      availability_score, reasons, eligible
    """
    organ_needed = recipient.get("organ_needed", "")
    need_type    = recipient.get("need_type", "Blood")
    urgency      = recipient.get("urgency", "Stable")

    results = []

    for donor in donors:
        if not donor.get("available", True):
            continue

        # Donation type gate
        if donor.get("donation_type") != need_type:
            continue

        # Organ availability gate (for organ donations)
        if need_type == "Organ" and not organ_available(donor, organ_needed):
            continue

        reasons = []

        # Blood compatibility
        b_score, b_reason = blood_score(
            donor["blood_type"], recipient["blood_type"], organ_needed
        )
        reasons.append(b_reason)

        # Location proximity
        l_score, l_reason = location_score(donor, recipient)
        reasons.append(l_reason)

        # Urgency
        u_score, u_reason = urgency_score(urgency)
        reasons.append(u_reason)

        # Availability (donor is available → full score)
        a_score = 1.0
        reasons.append("Donor is currently available ✅")

        # Eligibility: must have blood compatibility
        eligible = b_score > 0

        if not eligible:
            continue

        total = (
            b_score * SCORE_WEIGHT_BLOOD
            + l_score * SCORE_WEIGHT_LOCATION
            + u_score * SCORE_WEIGHT_URGENCY
            + a_score * SCORE_WEIGHT_AVAILABILITY
        )

        results.append({
            "donor":              donor,
            "recipient":          recipient,
            "total_score":        round(total, 1),
            "blood_score":        round(b_score * 100, 1),
            "location_score":     round(l_score * 100, 1),
            "urgency_score":      round(u_score * 100, 1),
            "availability_score": round(a_score * 100, 1),
            "reasons":            reasons,
            "eligible":           eligible,
        })

    results.sort(key=lambda x: x["total_score"], reverse=True)
    return results[:top_n]


def find_recipients_for_donor(donor: dict, recipients: list, top_n: int = 10) -> list[dict]:
    """Reverse matching — find recipients who need what this donor offers."""
    results = []
    for recipient in recipients:
        if recipient.get("status") != "Open":
            continue
        partial = match_donors_to_recipient(recipient, [donor], top_n=1)
        if partial:
            results.append(partial[0])
    results.sort(key=lambda x: x["total_score"], reverse=True)
    return results[:top_n]
