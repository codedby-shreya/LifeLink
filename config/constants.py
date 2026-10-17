"""
Global constants and configuration for the Blood & Organ Donor Matching Platform.
"""

# ── Blood type compatibility ─────────────────────────────────────────────────
# Key = recipient blood type  →  Value = list of compatible donor blood types
BLOOD_COMPATIBILITY = {
    "A+":  ["A+", "A-", "O+", "O-"],
    "A-":  ["A-", "O-"],
    "B+":  ["B+", "B-", "O+", "O-"],
    "B-":  ["B-", "O-"],
    "AB+": ["A+", "A-", "B+", "B-", "AB+", "AB-", "O+", "O-"],  # universal recipient
    "AB-": ["A-", "B-", "AB-", "O-"],
    "O+":  ["O+", "O-"],
    "O-":  ["O-"],  # universal donor (receives only O-)
}

ALL_BLOOD_TYPES = ["A+", "A-", "B+", "B-", "AB+", "AB-", "O+", "O-"]

# ── Organ compatibility (simplified rules) ───────────────────────────────────
# Same blood type or compatible, plus organ-specific tissue constraints (abstracted)
ORGAN_TYPES = [
    "Kidney",
    "Liver",
    "Heart",
    "Lung",
    "Pancreas",
    "Small Intestine",
    "Cornea",
    "Bone Marrow",
    "Skin",
    "Heart Valve",
]

# Organs where blood type must be an *exact* match (simplified clinical rule)
EXACT_BLOOD_MATCH_ORGANS = {"Heart", "Lung", "Pancreas", "Small Intestine"}

# Organs where universal donor (O-) rules apply (kidneys, liver)
COMPATIBLE_BLOOD_MATCH_ORGANS = {"Kidney", "Liver", "Cornea", "Bone Marrow", "Skin", "Heart Valve"}

# ── Donation types ───────────────────────────────────────────────────────────
DONATION_TYPES = ["Blood", "Organ"]

# ── Urgency levels ───────────────────────────────────────────────────────────
URGENCY_LEVELS = ["Critical (< 24 hrs)", "Urgent (1–3 days)", "Moderate (within a week)", "Stable"]

URGENCY_WEIGHT = {
    "Critical (< 24 hrs)": 4,
    "Urgent (1–3 days)": 3,
    "Moderate (within a week)": 2,
    "Stable": 1,
}

# ── Indian states / cities (common) ─────────────────────────────────────────
INDIAN_STATES = [
    "Andhra Pradesh", "Arunachal Pradesh", "Assam", "Bihar", "Chhattisgarh",
    "Goa", "Gujarat", "Haryana", "Himachal Pradesh", "Jharkhand",
    "Karnataka", "Kerala", "Madhya Pradesh", "Maharashtra", "Manipur",
    "Meghalaya", "Mizoram", "Nagaland", "Odisha", "Punjab",
    "Rajasthan", "Sikkim", "Tamil Nadu", "Telangana", "Tripura",
    "Uttar Pradesh", "Uttarakhand", "West Bengal",
    "Andaman and Nicobar Islands", "Chandigarh", "Dadra and Nagar Haveli",
    "Daman and Diu", "Delhi", "Jammu and Kashmir", "Ladakh",
    "Lakshadweep", "Puducherry",
]

# ── Match score weights ───────────────────────────────────────────────────────
SCORE_WEIGHT_BLOOD      = 40   # out of 100
SCORE_WEIGHT_LOCATION   = 30
SCORE_WEIGHT_URGENCY    = 20
SCORE_WEIGHT_AVAILABILITY = 10

# ── App metadata ─────────────────────────────────────────────────────────────
APP_TITLE       = "LifeLink – Blood & Organ Donor Matching"
APP_ICON        = "🩸"
APP_DESCRIPTION = (
    "An AI-powered platform connecting blood and organ donors with recipients "
    "through intelligent compatibility matching and real-time urgent request management."
)

GEMINI_MODEL = "gemini-3.6-flash"   # Gemini 3.6 Flash (latest model as of 2026)


# ═════════════════════════════════════════════════════════════════════════════
# Additions for the persistent / redesigned version of LifeLink.
# Everything above this line (blood rules, urgency weights, SCORE_WEIGHT_*)
# is unchanged from the original project.
# ═════════════════════════════════════════════════════════════════════════════

BRAND_NAME      = "LifeLink"
BRAND_TAGLINE   = "Care connects us all."
HOME_HEADLINE   = "A little care can change a life."
EMERGENCY_NUMBER_IN = "112"

GENDERS = ["Male", "Female", "Other"]

# Request lifecycle (unchanged values from the original app)
REQUEST_STATUSES = ["Open", "In Progress", "Fulfilled", "Cancelled"]
# Statuses a requester may set themselves with their tracking code
REQUESTER_SETTABLE_STATUSES = ["Fulfilled", "Cancelled"]

# Match lifecycle (unchanged values from the original app)
MATCH_STATUSES = ["Pending Contact", "Contacted", "In Progress", "Completed", "Failed"]

# Field limits (also enforced by CHECK constraints in db/schema.sql)
DONOR_MIN_AGE = 18
DONOR_MAX_AGE = 65
NOTES_MAX_LEN = 1000

# Admin session
ADMIN_IDLE_TIMEOUT_MINUTES = 30
