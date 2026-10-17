"""
LifeLink data access layer (repository).

Replaces the original session-state store with real persistence while keeping
the original function names where possible (add_donor, get_donors, save_match,
update_match_status, donors_to_df, ...).

Privacy model
  * Default reads return PUBLIC-SAFE records: no names, phone numbers, emails,
    patient names, hospital names or medical notes.
  * Private fields (include_private=True, *_to_df, get_matches, deletes,
    status changes by staff) require an authenticated administrator and raise
    PermissionDenied otherwise.
  * Donors / requesters manage their own record with a private access code
    that is shown once at registration and stored only as a hash.
"""

from __future__ import annotations

import datetime as dt
import json
import uuid
from typing import Any

import pandas as pd

from config.constants import (
    ALL_BLOOD_TYPES, DONATION_TYPES, GENDERS, MATCH_STATUSES, ORGAN_TYPES,
    REQUEST_STATUSES, REQUESTER_SETTABLE_STATUSES, URGENCY_LEVELS, URGENCY_WEIGHT,
)
from utils import auth
from utils import database as database
from utils.database import (  # re-exported for callers
    DatabaseUnavailable, SchemaMissing, UniqueViolation, transaction,
)
from utils.validators import normalize_phone

__all__ = [
    "DatabaseUnavailable", "SchemaMissing", "DuplicateError", "NotFoundError",
    "init_db", "add_donor", "get_donors", "get_donor_by_id", "update_donor_availability",
    "set_my_availability", "verify_access", "add_recipient", "get_recipients",
    "get_recipient_by_id", "update_recipient_status", "set_my_request_status",
    "get_my_request", "save_match", "get_matches", "update_match_status",
    "get_public_stats", "donor_blood_counts", "donors_to_df", "recipients_to_df",
    "matches_to_df", "delete_record", "get_audit_log", "log_audit",
]


class DuplicateError(Exception):
    """kind: 'donor' | 'request' | 'resubmit'"""

    def __init__(self, kind: str, message: str):
        super().__init__(message)
        self.kind = kind


class NotFoundError(LookupError):
    pass


# ── Row normalisation ────────────────────────────────────────────────────────

_TS_COLS = {"registered_at", "posted_at", "matched_at", "updated_at", "consent_at", "at", "attempted_at"}
_JSON_COLS = {"organs", "details"}
_BOOL_COLS = {"available", "success"}


def _norm(row: dict | None) -> dict | None:
    if row is None:
        return None
    out: dict[str, Any] = {}
    for key, val in row.items():
        if isinstance(val, uuid.UUID):
            val = str(val)
        elif key in _TS_COLS and isinstance(val, str):
            val = dt.datetime.fromisoformat(val)
        elif key in _JSON_COLS and isinstance(val, str):
            val = json.loads(val)
        elif key in _BOOL_COLS and val is not None:
            val = bool(val)
        elif key == "score" and val is not None:
            val = float(val)
        elif key in ("n", "total_donors", "available_donors", "total_requests", "open_requests",
                     "total_matches", "successful_matches", "fulfilled_requests") and val is not None:
            val = int(val)
        if key in _TS_COLS and isinstance(val, dt.datetime) and val.tzinfo is None:
            val = val.replace(tzinfo=dt.timezone.utc)
        out[key] = val
    return out


def _norms(rows: list[dict]) -> list[dict]:
    return [_norm(r) for r in rows]  # type: ignore[misc]


def _now() -> dt.datetime:
    return database.utcnow()


def _require_admin() -> None:
    auth.require_admin()


# ── Setup ────────────────────────────────────────────────────────────────────

def init_db() -> None:
    """Verify (SQLite: create) the schema. Never clears or recreates data."""
    database.ensure_schema()


# ── Column sets ──────────────────────────────────────────────────────────────

_DONOR_PUBLIC = ("id AS uid, public_id AS id, blood_type, donation_type, organs, city, state, "
                 "available, registered_at")
_DONOR_PRIVATE = _DONOR_PUBLIC + ", name, age, gender, phone, email, medical_notes, updated_at"

_REQ_PUBLIC = ("id AS uid, public_id AS id, blood_type, need_type, organ_needed, city, state, "
               "urgency, status, posted_at")
_REQ_PRIVATE = _REQ_PUBLIC + ", name, age, gender, hospital, phone, email, medical_notes, updated_at"


# ── Donors ───────────────────────────────────────────────────────────────────

def add_donor(
    name: str, age: int, gender: str, blood_type: str, donation_type: str, organs: list,
    city: str, state: str, phone: str, email: str, medical_notes: str = "",
    available: bool = True, submit_key: str | None = None,
) -> dict:
    """
    Create a donor. Returns the public-safe record plus a one-time `access_code`.
    Raises DuplicateError when the phone number is already registered or the
    same form submission is replayed.
    """
    if blood_type not in ALL_BLOOD_TYPES or donation_type not in DONATION_TYPES or gender not in GENDERS:
        raise ValueError("Invalid blood type, donation type or gender.")
    organs = [o for o in (organs or []) if o in ORGAN_TYPES]
    if donation_type == "Organ" and not organs:
        raise ValueError("Select at least one organ.")
    if donation_type == "Blood":
        organs = []

    uid, code, now = str(uuid.uuid4()), auth.new_access_code(), _now()
    phone_norm = normalize_phone(phone)
    with transaction() as tx:
        if submit_key and tx.one("select 1 as x from donors where submit_key = %s", (submit_key,)):
            raise DuplicateError("resubmit", "This registration was already submitted.")
        if tx.one("select 1 as x from donors where phone_norm = %s", (phone_norm,)):
            raise DuplicateError("donor", "A donor with this phone number is already registered.")
        public_id = auth.new_public_id("D")
        while tx.one("select 1 as x from donors where public_id = %s", (public_id,)):
            public_id = auth.new_public_id("D")
        try:
            tx.execute(
                "insert into donors (id, public_id, name, age, gender, blood_type, donation_type, organs, "
                "city, state, phone, phone_norm, email, medical_notes, available, access_code_hash, "
                "submit_key, consent_at, registered_at, updated_at) "
                "values (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)",
                (uid, public_id, name, int(age), gender, blood_type, donation_type, tx.json(organs),
                 city, state, phone, phone_norm, email, medical_notes, bool(available),
                 auth.hash_secret(auth.normalize_code(code)), submit_key, now, now, now),
            )
        except UniqueViolation as exc:
            kind = "resubmit" if "submit_key" in exc.detail else "donor"
            raise DuplicateError(kind, "This donor is already registered.") from exc
    return {"uid": uid, "id": public_id, "blood_type": blood_type, "donation_type": donation_type,
            "organs": organs, "city": city, "state": state, "available": bool(available),
            "registered_at": now, "access_code": code}


def get_donors(available_only: bool = False, include_private: bool = False) -> list[dict]:
    if include_private:
        _require_admin()
    sql = f"select {_DONOR_PRIVATE if include_private else _DONOR_PUBLIC} from donors"
    params: tuple = ()
    if available_only:
        sql += " where available = %s"
        params = (True,)
    sql += " order by registered_at desc"
    with transaction() as tx:
        return _norms(tx.query(sql, params))


def get_donor_by_id(donor_id: str, include_private: bool = False) -> dict | None:
    if include_private:
        _require_admin()
    cols = _DONOR_PRIVATE if include_private else _DONOR_PUBLIC
    with transaction() as tx:
        return _norm(tx.one(f"select {cols} from donors where public_id = %s", (donor_id.strip().upper(),)))


def update_donor_availability(donor_id: str, available: bool) -> None:
    """Staff action (admin only)."""
    _require_admin()
    with transaction() as tx:
        n = tx.execute("update donors set available = %s, updated_at = %s where public_id = %s",
                       (bool(available), _now(), donor_id))
        if not n:
            raise NotFoundError("Donor not found.")
    log_audit("donor.availability", "donor", donor_id, f"available={bool(available)}")


# ── Private access codes (self-service) ──────────────────────────────────────

_TABLES = {"donor": "donors", "recipient": "recipients"}


def verify_access(kind: str, public_id: str, code: str) -> bool:
    """
    Check a donor / requester's private access code. Throttled per record:
    after 5 wrong codes the record is locked for 15 minutes. Wrong ID and wrong
    code are indistinguishable to the caller.
    """
    table = _TABLES[kind]
    public_id = (public_id or "").strip().upper()
    scope = f"{kind}:{public_id}"
    if auth.is_locked(scope):
        raise PermissionError("Too many incorrect attempts. Please try again in about 15 minutes.")
    with transaction() as tx:
        row = tx.one(f"select access_code_hash from {table} where public_id = %s", (public_id,))
    ok = bool(row) and auth.verify_secret(auth.normalize_code(code), row["access_code_hash"])
    auth.record_attempt(scope, ok)
    return ok


def set_my_availability(donor_id: str, code: str, available: bool) -> bool:
    if not verify_access("donor", donor_id, code):
        return False
    with transaction() as tx:
        tx.execute("update donors set available = %s, updated_at = %s where public_id = %s",
                   (bool(available), _now(), donor_id.strip().upper()))
    return True


# ── Recipients / requests ────────────────────────────────────────────────────

def add_recipient(
    name: str, age: int, gender: str, blood_type: str, need_type: str, organ_needed: str,
    city: str, state: str, hospital: str, phone: str, email: str, urgency: str,
    medical_notes: str = "", submit_key: str | None = None,
) -> dict:
    if (blood_type not in ALL_BLOOD_TYPES or need_type not in DONATION_TYPES or gender not in GENDERS
            or urgency not in URGENCY_LEVELS):
        raise ValueError("Invalid blood type, need type, gender or urgency.")
    if need_type == "Organ" and organ_needed not in ORGAN_TYPES:
        raise ValueError("Select the organ required.")
    if need_type == "Blood":
        organ_needed = ""

    uid, code, now = str(uuid.uuid4()), auth.new_access_code(), _now()
    phone_norm = normalize_phone(phone)
    with transaction() as tx:
        if submit_key and tx.one("select 1 as x from recipients where submit_key = %s", (submit_key,)):
            raise DuplicateError("resubmit", "This request was already submitted.")
        if tx.one(
            "select 1 as x from recipients where phone_norm = %s and lower(name) = %s and blood_type = %s "
            "and need_type = %s and organ_needed = %s and status in (%s, %s)",
            (phone_norm, name.lower(), blood_type, need_type, organ_needed, "Open", "In Progress"),
        ):
            raise DuplicateError("request", "An active request for this patient already exists.")
        public_id = auth.new_public_id("R")
        while tx.one("select 1 as x from recipients where public_id = %s", (public_id,)):
            public_id = auth.new_public_id("R")
        try:
            tx.execute(
                "insert into recipients (id, public_id, name, age, gender, blood_type, need_type, organ_needed, "
                "city, state, hospital, phone, phone_norm, email, urgency, medical_notes, status, "
                "access_code_hash, submit_key, consent_at, posted_at, updated_at) "
                "values (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)",
                (uid, public_id, name, int(age), gender, blood_type, need_type, organ_needed, city, state,
                 hospital, phone, phone_norm, email, urgency, medical_notes, "Open",
                 auth.hash_secret(auth.normalize_code(code)), submit_key, now, now, now),
            )
        except UniqueViolation as exc:
            raise DuplicateError("resubmit", "This request was already submitted.") from exc
    return {"uid": uid, "id": public_id, "blood_type": blood_type, "need_type": need_type,
            "organ_needed": organ_needed, "city": city, "state": state, "urgency": urgency,
            "status": "Open", "posted_at": now, "access_code": code}


def get_recipients(open_only: bool = False, include_private: bool = False) -> list[dict]:
    if include_private:
        _require_admin()
    sql = f"select {_REQ_PRIVATE if include_private else _REQ_PUBLIC} from recipients"
    params: tuple = ()
    if open_only:
        sql += " where status = %s"
        params = ("Open",)
    sql += " order by posted_at desc"
    with transaction() as tx:
        rows = _norms(tx.query(sql, params))
    rows.sort(key=lambda r: URGENCY_WEIGHT.get(r["urgency"], 0), reverse=True)  # stable: newest first within urgency
    return rows


def get_recipient_by_id(recipient_id: str, include_private: bool = False) -> dict | None:
    if include_private:
        _require_admin()
    cols = _REQ_PRIVATE if include_private else _REQ_PUBLIC
    with transaction() as tx:
        return _norm(tx.one(f"select {cols} from recipients where public_id = %s",
                            (recipient_id.strip().upper(),)))


def get_my_request(request_id: str, code: str) -> dict | None:
    """Requester's own view (needs the tracking code): status + saved-match count, no donor details."""
    if not verify_access("recipient", request_id, code):
        return None
    with transaction() as tx:
        row = tx.one(
            f"select {_REQ_PUBLIC}, hospital, updated_at from recipients where public_id = %s",
            (request_id.strip().upper(),),
        )
        rec = _norm(row)
        n = tx.one("select count(*) as n from matches where recipient_id = %s", (rec["uid"],))
        rec["saved_matches"] = int(n["n"])
        done = tx.one("select count(*) as n from matches where recipient_id = %s and status = %s",
                      (rec["uid"], "Contacted"))
        rec["contacted_matches"] = int(done["n"])
    return rec


def update_recipient_status(recipient_id: str, status: str) -> None:
    """Staff action (admin only)."""
    _require_admin()
    if status not in REQUEST_STATUSES:
        raise ValueError("Unknown status.")
    with transaction() as tx:
        n = tx.execute("update recipients set status = %s, updated_at = %s where public_id = %s",
                       (status, _now(), recipient_id))
        if not n:
            raise NotFoundError("Request not found.")
    log_audit("request.status", "request", recipient_id, f"status={status}")


def set_my_request_status(request_id: str, code: str, status: str) -> bool:
    """Requester may mark their own open request Fulfilled or Cancelled."""
    if status not in REQUESTER_SETTABLE_STATUSES:
        raise ValueError("You can only mark a request as Fulfilled or Cancelled.")
    if not verify_access("recipient", request_id, code):
        return False
    with transaction() as tx:
        tx.execute(
            "update recipients set status = %s, updated_at = %s "
            "where public_id = %s and status in (%s, %s)",
            (status, _now(), request_id.strip().upper(), "Open", "In Progress"),
        )
    return True


# ── Matches ──────────────────────────────────────────────────────────────────

def save_match(donor_id: str, recipient_id: str, score: float, details: dict) -> dict:
    """
    Persist a match (public ids in). One match per donor/request pair: saving
    the same pair again returns the existing record with created=False.
    Only available donors and open requests can be matched.
    """
    now = _now()
    with transaction() as tx:
        donor = tx.one("select id, available from donors where public_id = %s", (donor_id,))
        recip = tx.one("select id, status from recipients where public_id = %s", (recipient_id,))
        if not donor or not recip:
            raise NotFoundError("Donor or request not found.")
        if not bool(donor["available"]):
            raise ValueError("This donor is not currently available.")
        if recip["status"] != "Open":
            raise ValueError("This request is no longer open.")
        d_uid, r_uid = str(donor["id"]), str(recip["id"])
        existing = tx.one("select public_id, status, score, matched_at from matches "
                          "where donor_id = %s and recipient_id = %s", (d_uid, r_uid))
        if existing:
            rec = _norm(existing)
            return {"id": rec["public_id"], "donor_id": donor_id, "recipient_id": recipient_id,
                    "score": rec["score"], "status": rec["status"], "matched_at": rec["matched_at"],
                    "created": False}
        public_id = auth.new_public_id("M")
        while tx.one("select 1 as x from matches where public_id = %s", (public_id,)):
            public_id = auth.new_public_id("M")
        payload = dict(details or {})
        payload.setdefault("schema_version", 1)
        tx.execute(
            "insert into matches (id, public_id, donor_id, recipient_id, score, details, status, "
            "matched_at, updated_at) values (%s,%s,%s,%s,%s,%s,%s,%s,%s)",
            (str(uuid.uuid4()), public_id, d_uid, r_uid, round(float(score), 1), tx.json(payload),
             "Pending Contact", now, now),
        )
    return {"id": public_id, "donor_id": donor_id, "recipient_id": recipient_id,
            "score": round(float(score), 1), "status": "Pending Contact", "matched_at": now, "created": True}


_MATCH_SELECT = (
    "select m.id as uid, m.public_id as id, m.score, m.details, m.status, m.matched_at, m.updated_at, "
    "d.public_id as donor_id, d.name as donor_name, d.phone as donor_phone, d.email as donor_email, "
    "d.blood_type as donor_blood, d.city as donor_city, d.state as donor_state, "
    "r.public_id as recipient_id, r.name as recipient_name, r.phone as recipient_phone, "
    "r.hospital as recipient_hospital, r.blood_type as recipient_blood, r.need_type, r.organ_needed, "
    "r.urgency, r.city as recipient_city, r.state as recipient_state "
    "from matches m join donors d on d.id = m.donor_id join recipients r on r.id = m.recipient_id "
)


def get_matches() -> list[dict]:
    """Admin only — includes both parties' contact details for coordination."""
    _require_admin()
    with transaction() as tx:
        return _norms(tx.query(_MATCH_SELECT + "order by m.matched_at desc"))


def update_match_status(match_id: str, status: str) -> None:
    _require_admin()
    if status not in MATCH_STATUSES:
        raise ValueError("Unknown match status.")
    with transaction() as tx:
        n = tx.execute("update matches set status = %s, updated_at = %s where public_id = %s",
                       (status, _now(), match_id))
        if not n:
            raise NotFoundError("Match not found.")
    log_audit("match.status", "match", match_id, f"status={status}")


# ── Statistics ───────────────────────────────────────────────────────────────

def get_public_stats() -> dict:
    """Aggregate counts only — safe for the public home page. Real data, zeros if empty."""
    with transaction() as tx:
        row = tx.one(
            "select (select count(*) from donors) as total_donors, "
            "(select count(*) from donors where available = %s) as available_donors, "
            "(select count(*) from recipients) as total_requests, "
            "(select count(*) from recipients where status = %s) as open_requests, "
            "(select count(*) from matches) as total_matches, "
            "(select count(*) from matches where status = %s) as successful_matches, "
            "(select count(*) from recipients where status = %s) as fulfilled_requests",
            (True, "Open", "Completed", "Fulfilled"),
        )
    return _norm(row) or {}


def donor_blood_counts() -> dict[str, int]:
    """Available donors per blood group (anonymous aggregate)."""
    with transaction() as tx:
        rows = tx.query("select blood_type, count(*) as n from donors where available = %s group by blood_type",
                        (True,))
    counts = {bt: 0 for bt in ALL_BLOOD_TYPES}
    for r in rows:
        counts[r["blood_type"]] = int(r["n"])
    return counts


# ── DataFrames for the admin dashboard (admin only) ──────────────────────────

def donors_to_df() -> pd.DataFrame:
    rows = get_donors(include_private=True)
    if not rows:
        return pd.DataFrame()
    df = pd.DataFrame(rows).drop(columns=["uid"])
    df["organs"] = df["organs"].apply(lambda x: ", ".join(x) if x else "—")
    return df


def recipients_to_df() -> pd.DataFrame:
    rows = get_recipients(include_private=True)
    return pd.DataFrame(rows).drop(columns=["uid"]) if rows else pd.DataFrame()


def matches_to_df() -> pd.DataFrame:
    rows = get_matches()
    if not rows:
        return pd.DataFrame()
    return pd.DataFrame([{
        "Match ID": m["id"],
        "Donor ID": m["donor_id"], "Donor": m["donor_name"], "Donor Blood": m["donor_blood"],
        "Donor Location": f"{m['donor_city']} / {m['donor_state']}",
        "Request ID": m["recipient_id"], "Patient": m["recipient_name"],
        "Need": m["organ_needed"] or m["need_type"], "Urgency": m["urgency"],
        "Score": m["score"], "Status": m["status"], "Matched At": m["matched_at"],
    } for m in rows])


# ── Administration: deletes & audit log ──────────────────────────────────────

def log_audit(action: str, entity: str = "", entity_id: str = "", detail: str = "") -> None:
    with transaction() as tx:
        tx.execute("insert into audit_log (id, at, actor, action, entity, entity_id, detail) "
                   "values (%s,%s,%s,%s,%s,%s,%s)",
                   (str(uuid.uuid4()), _now(), "admin", action, entity, entity_id, detail))


def delete_record(kind: str, public_id: str) -> None:
    """Permanently delete a donor / request / match (admin only; cascades to its matches)."""
    _require_admin()
    table = {"donor": "donors", "request": "recipients", "match": "matches"}[kind]
    with transaction() as tx:
        n = tx.execute(f"delete from {table} where public_id = %s", (public_id,))
        if not n:
            raise NotFoundError("Record not found.")
    log_audit(f"{kind}.delete", kind, public_id)


def get_audit_log(limit: int = 100) -> list[dict]:
    _require_admin()
    with transaction() as tx:
        return _norms(tx.query("select at, actor, action, entity, entity_id, detail from audit_log "
                               "order by at desc limit %s", (int(limit),)))
