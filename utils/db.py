"""
In-memory + session-state backed data store for the LifeLink platform.
All records are kept in st.session_state so they persist across reruns
within the same browser session.
"""

import uuid
import datetime
import streamlit as st
import pandas as pd


# ── Schema helpers ────────────────────────────────────────────────────────────

def _new_id() -> str:
    return str(uuid.uuid4())[:8].upper()


def _now() -> str:
    return datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")


# ── Initialise session-state tables ──────────────────────────────────────────

def init_db():
    """Call once at app startup to ensure all tables exist in session_state."""
    defaults = {
        "donors": [],          # list[dict]
        "recipients": [],      # list[dict]
        "matches": [],         # list[dict]
        "chat_history": [],    # list[dict]  {role, content, ts}
    }
    for key, val in defaults.items():
        if key not in st.session_state:
            st.session_state[key] = val


# ── Donor CRUD ────────────────────────────────────────────────────────────────

def add_donor(
    name: str,
    age: int,
    gender: str,
    blood_type: str,
    donation_type: str,       # "Blood" | "Organ"
    organs: list,             # empty list if blood donation
    city: str,
    state: str,
    phone: str,
    email: str,
    medical_notes: str = "",
    available: bool = True,
) -> dict:
    record = {
        "id": _new_id(),
        "name": name,
        "age": age,
        "gender": gender,
        "blood_type": blood_type,
        "donation_type": donation_type,
        "organs": organs,
        "city": city,
        "state": state,
        "phone": phone,
        "email": email,
        "medical_notes": medical_notes,
        "available": available,
        "registered_at": _now(),
    }
    st.session_state["donors"].append(record)
    return record


def get_donors(available_only: bool = False) -> list:
    donors = st.session_state.get("donors", [])
    if available_only:
        donors = [d for d in donors if d["available"]]
    return donors


def get_donor_by_id(donor_id: str) -> dict | None:
    for d in st.session_state.get("donors", []):
        if d["id"] == donor_id:
            return d
    return None


def update_donor_availability(donor_id: str, available: bool):
    for d in st.session_state.get("donors", []):
        if d["id"] == donor_id:
            d["available"] = available
            break


def donors_to_df() -> pd.DataFrame:
    donors = st.session_state.get("donors", [])
    if not donors:
        return pd.DataFrame()
    df = pd.DataFrame(donors)
    df["organs"] = df["organs"].apply(lambda x: ", ".join(x) if x else "—")
    return df


# ── Recipient CRUD ────────────────────────────────────────────────────────────

def add_recipient(
    name: str,
    age: int,
    gender: str,
    blood_type: str,
    need_type: str,           # "Blood" | "Organ"
    organ_needed: str,        # empty string if blood
    city: str,
    state: str,
    hospital: str,
    phone: str,
    email: str,
    urgency: str,
    medical_notes: str = "",
) -> dict:
    record = {
        "id": _new_id(),
        "name": name,
        "age": age,
        "gender": gender,
        "blood_type": blood_type,
        "need_type": need_type,
        "organ_needed": organ_needed,
        "city": city,
        "state": state,
        "hospital": hospital,
        "phone": phone,
        "email": email,
        "urgency": urgency,
        "medical_notes": medical_notes,
        "status": "Open",
        "posted_at": _now(),
    }
    st.session_state["recipients"].append(record)
    return record


def get_recipients(open_only: bool = False) -> list:
    recipients = st.session_state.get("recipients", [])
    if open_only:
        recipients = [r for r in recipients if r["status"] == "Open"]
    return recipients


def get_recipient_by_id(recipient_id: str) -> dict | None:
    for r in st.session_state.get("recipients", []):
        if r["id"] == recipient_id:
            return r
    return None


def update_recipient_status(recipient_id: str, status: str):
    for r in st.session_state.get("recipients", []):
        if r["id"] == recipient_id:
            r["status"] = status
            break


def recipients_to_df() -> pd.DataFrame:
    recipients = st.session_state.get("recipients", [])
    if not recipients:
        return pd.DataFrame()
    return pd.DataFrame(recipients)


# ── Match CRUD ────────────────────────────────────────────────────────────────

def save_match(donor_id: str, recipient_id: str, score: float, details: dict) -> dict:
    record = {
        "id": _new_id(),
        "donor_id": donor_id,
        "recipient_id": recipient_id,
        "score": round(score, 1),
        "details": details,
        "matched_at": _now(),
        "status": "Pending Contact",
    }
    # Avoid duplicate matches
    existing_ids = {(m["donor_id"], m["recipient_id"]) for m in st.session_state.get("matches", [])}
    if (donor_id, recipient_id) not in existing_ids:
        st.session_state["matches"].append(record)
    return record


def get_matches() -> list:
    return st.session_state.get("matches", [])


def update_match_status(match_id: str, status: str):
    for m in st.session_state.get("matches", []):
        if m["id"] == match_id:
            m["status"] = status
            break


def matches_to_df() -> pd.DataFrame:
    matches = st.session_state.get("matches", [])
    if not matches:
        return pd.DataFrame()
    rows = []
    for m in matches:
        donor   = get_donor_by_id(m["donor_id"])   or {}
        recip   = get_recipient_by_id(m["recipient_id"]) or {}
        rows.append({
            "Match ID":      m["id"],
            "Donor":         donor.get("name", "—"),
            "Donor Blood":   donor.get("blood_type", "—"),
            "Donor Location": f"{donor.get('city', '')} / {donor.get('state', '')}",
            "Recipient":     recip.get("name", "—"),
            "Need":          recip.get("organ_needed") or recip.get("need_type", "—"),
            "Urgency":       recip.get("urgency", "—"),
            "Score":         m["score"],
            "Status":        m["status"],
            "Matched At":    m["matched_at"],
        })
    return pd.DataFrame(rows)


# ── Chat history ──────────────────────────────────────────────────────────────

def append_chat(role: str, content: str):
    st.session_state["chat_history"].append({
        "role": role,
        "content": content,
        "ts": _now(),
    })


def get_chat_history() -> list:
    return st.session_state.get("chat_history", [])


def clear_chat():
    st.session_state["chat_history"] = []
