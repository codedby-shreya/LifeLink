"""
Authentication and authorisation helpers.

* Administrator login — password from ADMIN_PASSWORD_HASH (recommended) or
  ADMIN_PASSWORD, read from environment / Streamlit secrets. The authenticated
  flag lives in server-side st.session_state (the browser cannot forge it) and
  expires after an idle timeout.
* Private access codes — donors and requesters receive a random code when they
  register. Only its PBKDF2 hash is stored.
* Throttling — failed attempts are recorded in the database and lock the scope
  for a while, so codes and passwords cannot be brute-forced.
"""

from __future__ import annotations

import datetime as dt
import hashlib
import hmac
import secrets
import time
import uuid

from config.constants import ADMIN_IDLE_TIMEOUT_MINUTES
from utils import database as database

_ALPHABET = "ABCDEFGHJKMNPQRSTUVWXYZ23456789"   # no 0/O/1/I/L — easy to read aloud
_PBKDF2_ITERATIONS = 200_000

MAX_FAILURES = 5
LOCK_WINDOW_MINUTES = 15


class PermissionDenied(PermissionError):
    """Raised when an admin-only operation is attempted without admin rights."""


# ── Secrets: hashing & ids ───────────────────────────────────────────────────

def random_token(length: int = 8) -> str:
    return "".join(secrets.choice(_ALPHABET) for _ in range(length))


def new_public_id(kind: str) -> str:
    """kind: 'D' donor, 'R' request, 'M' match  →  LL-D-7K2M9Q4X"""
    return f"LL-{kind}-{random_token(8)}"


def new_access_code() -> str:
    """Human-friendly one-time-visible code, e.g. K7M2-PQ4R."""
    raw = random_token(8)
    return f"{raw[:4]}-{raw[4:]}"


def normalize_code(code: str) -> str:
    return "".join(ch for ch in (code or "").upper() if ch.isalnum())


def hash_secret(secret: str, iterations: int = _PBKDF2_ITERATIONS) -> str:
    salt = secrets.token_hex(16)
    digest = hashlib.pbkdf2_hmac("sha256", secret.encode(), bytes.fromhex(salt), iterations).hex()
    return f"pbkdf2_sha256${iterations}${salt}${digest}"


def verify_secret(secret: str, stored: str) -> bool:
    try:
        scheme, iterations, salt, digest = stored.split("$")
        if scheme != "pbkdf2_sha256":
            return False
        candidate = hashlib.pbkdf2_hmac("sha256", secret.encode(), bytes.fromhex(salt), int(iterations)).hex()
        return hmac.compare_digest(candidate, digest)
    except (ValueError, TypeError):
        return False


# ── Throttling ───────────────────────────────────────────────────────────────

def record_attempt(scope: str, success: bool) -> None:
    now = database.utcnow()
    with database.transaction() as tx:
        tx.execute(
            "insert into auth_attempts (id, scope, success, attempted_at) values (%s, %s, %s, %s)",
            (str(uuid.uuid4()), scope, success, now),
        )
        # housekeeping: forget attempts older than a day
        tx.execute(
            "delete from auth_attempts where attempted_at < %s",
            (now - dt.timedelta(days=1),),
        )


def is_locked(scope: str) -> bool:
    since = database.utcnow() - dt.timedelta(minutes=LOCK_WINDOW_MINUTES)
    with database.transaction() as tx:
        # a successful attempt resets the counter
        last_ok = tx.one(
            "select max(attempted_at) as t from auth_attempts where scope = %s and success = %s",
            (scope, True),
        )
        row = tx.one(
            "select count(*) as n from auth_attempts "
            "where scope = %s and success = %s and attempted_at > %s",
            (scope, False, since),
        )
    failures = int(row["n"]) if row else 0
    if last_ok and last_ok["t"]:
        # count only failures after the last success
        with database.transaction() as tx:
            row = tx.one(
                "select count(*) as n from auth_attempts "
                "where scope = %s and success = %s and attempted_at > %s and attempted_at > %s",
                (scope, False, since, last_ok["t"]),
            )
        failures = int(row["n"]) if row else 0
    return failures >= MAX_FAILURES


# ── Administrator session ────────────────────────────────────────────────────

def _session() -> dict:
    import streamlit as st

    return st.session_state


def admin_configured() -> bool:
    return bool(database.get_setting("ADMIN_PASSWORD_HASH") or database.get_setting("ADMIN_PASSWORD"))


def _check_admin_password(password: str) -> bool:
    stored_hash = database.get_setting("ADMIN_PASSWORD_HASH")
    if stored_hash:
        return verify_secret(password, stored_hash)
    plain = database.get_setting("ADMIN_PASSWORD")
    return bool(plain) and hmac.compare_digest(password.encode(), plain.encode())


def admin_login(password: str) -> tuple[bool, str]:
    """Returns (success, message). Never reveals whether the password was close."""
    if not admin_configured():
        return False, "Administrator access has not been configured on this deployment."
    if is_locked("admin"):
        return False, f"Too many failed attempts. Please wait about {LOCK_WINDOW_MINUTES} minutes and try again."
    ok = _check_admin_password(password or "")
    record_attempt("admin", ok)
    if not ok:
        time.sleep(0.6)  # small fixed delay slows scripted guessing
        return False, "That password is not correct."
    sess = _session()
    sess["_admin_until"] = time.time() + ADMIN_IDLE_TIMEOUT_MINUTES * 60
    return True, "Signed in."


def is_admin() -> bool:
    try:
        sess = _session()
    except Exception:
        return False
    until = sess.get("_admin_until", 0)
    if until and time.time() < until:
        sess["_admin_until"] = time.time() + ADMIN_IDLE_TIMEOUT_MINUTES * 60  # sliding window
        return True
    if until:
        sess.pop("_admin_until", None)
    return False


def admin_logout() -> None:
    _session().pop("_admin_until", None)


def require_admin() -> None:
    if not is_admin():
        raise PermissionDenied("Administrator sign-in required.")
