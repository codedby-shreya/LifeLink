"""Input validation and normalisation helpers (pure functions, no Streamlit)."""

from __future__ import annotations

import re

from config.constants import NOTES_MAX_LEN

_NAME_RE = re.compile(r"[^\W\d_](?:[^\W\d_]|[ .'\-])*")
_EMAIL_RE = re.compile(r"[A-Za-z0-9._%+\-]+@[A-Za-z0-9\-]+(?:\.[A-Za-z0-9\-]+)*\.[A-Za-z]{2,}")
_CTRL_RE = re.compile(r"[\x00-\x08\x0b\x0c\x0e-\x1f\x7f]")


def clean_text(value: str | None, max_len: int = 200) -> str:
    """Strip control characters, trim whitespace, enforce a maximum length."""
    text = _CTRL_RE.sub("", value or "").strip()
    return text[:max_len]


def validate_name(value: str, label: str = "Name") -> tuple[str, str | None]:
    text = re.sub(r"\s+", " ", clean_text(value, 120))
    if not text:
        return text, f"{label} is required."
    if len(text) < 2 or len(text) > 80:
        return text, f"{label} must be between 2 and 80 characters."
    if not _NAME_RE.fullmatch(text):
        return text, f"{label} can contain letters, spaces, apostrophes, dots and hyphens only."
    return text, None


def validate_place(value: str, label: str = "City") -> tuple[str, str | None]:
    text = re.sub(r"\s+", " ", clean_text(value, 100))
    if not text:
        return text, f"{label} is required."
    if len(text) < 2 or len(text) > 60:
        return text, f"{label} must be between 2 and 60 characters."
    if not _NAME_RE.fullmatch(text):
        return text, f"{label} can contain letters, spaces, dots and hyphens only."
    return text, None


def validate_hospital(value: str) -> tuple[str, str | None]:
    text = re.sub(r"\s+", " ", clean_text(value, 150))
    if not text:
        return text, "Hospital name is required."
    if len(text) < 2 or len(text) > 120:
        return text, "Hospital name must be between 2 and 120 characters."
    return text, None


def phone_digits(raw: str) -> str:
    return re.sub(r"\D", "", raw or "")


def normalize_phone(raw: str) -> str:
    """Last 10 digits — the key used to detect duplicate registrations."""
    return phone_digits(raw)[-10:]


def validate_phone(raw: str, label: str = "Phone number", allow_landline: bool = False) -> tuple[str, str | None]:
    """
    Accepts Indian numbers: optional +91 / 91 / 0 prefix, then 10 digits.
    Mobile numbers start with 6-9. Landlines (STD + number, 10 digits) are
    accepted only when allow_landline=True (hospital contact desks).
    Returns (display_value, error).
    """
    text = clean_text(raw, 30)
    if not text:
        return text, f"{label} is required."
    if re.search(r"[^\d+\-\s()]", text):
        return text, f"{label} can contain digits, spaces, + and - only."
    digits = phone_digits(text)
    if digits.startswith("91") and len(digits) == 12:
        digits = digits[2:]
    elif digits.startswith("0") and len(digits) == 11:
        digits = digits[1:]
    if len(digits) != 10:
        return text, f"{label} must have 10 digits (optionally starting with +91)."
    if not allow_landline and digits[0] not in "6789":
        return text, f"{label} must be a valid Indian mobile number (starts with 6, 7, 8 or 9)."
    return f"+91 {digits[:5]} {digits[5:]}", None


def validate_email(raw: str, required: bool = False) -> tuple[str, str | None]:
    text = clean_text(raw, 254).lower()
    if not text:
        return "", "Email address is required." if required else None
    if not _EMAIL_RE.fullmatch(text):
        return text, "Enter a valid email address, for example name@example.com."
    return text, None


def validate_notes(raw: str, required: bool = False, label: str = "Notes") -> tuple[str, str | None]:
    text = clean_text(raw, NOTES_MAX_LEN + 1)
    if required and not text:
        return text, f"{label} are required."
    if len(text) > NOTES_MAX_LEN:
        return text[:NOTES_MAX_LEN], f"{label} must be {NOTES_MAX_LEN} characters or fewer."
    return text, None
