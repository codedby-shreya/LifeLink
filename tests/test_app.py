"""End-to-end page tests using Streamlit's headless AppTest (SQLite backend)."""
import time
from pathlib import Path

import pytest
from streamlit.testing.v1 import AppTest

from utils import auth, db

APP = str(Path(__file__).resolve().parent.parent / "app.py")
VIEWS = ["home", "donor_registration", "recipient_request", "matching_engine", "ai_assistant", "admin_dashboard"]


@pytest.fixture(autouse=True)
def env(tmp_path, monkeypatch):
    from utils import database
    database.reset_connections()
    for var in ("DATABASE_URL", "DB_BACKEND", "GEMINI_API_KEY", "ADMIN_PASSWORD", "ADMIN_PASSWORD_HASH"):
        monkeypatch.delenv(var, raising=False)
    monkeypatch.setenv("SQLITE_PATH", str(tmp_path / "app.db"))
    database.ensure_schema()
    yield


def view(name: str) -> AppTest:
    script = f"""
import streamlit as st
from utils import ui
ui.inject_css()
from views.{name} import render
render()
"""
    return AppTest.from_string(script, default_timeout=30)


def text_of(at: AppTest) -> str:
    parts = [m.value for m in at.markdown] + [e.value for e in at.error] + [w.value for w in at.warning]
    parts += [c.value for c in at.caption]
    return "\n".join(parts)


def by_label(widgets, prefix):
    return next(w for w in widgets if w.label.startswith(prefix))


def fill_donor(at, name="Ravi Kumar", phone="98765 43210", city="Patna", consent=True):
    by_label(at.text_input, "Full name").set_value(name)
    by_label(at.text_input, "Mobile").set_value(phone)
    by_label(at.text_input, "City").set_value(city)
    if consent:
        at.checkbox[0].check()


def click(at, label):
    next(b for b in at.button if b.label == label).click()


# ── 1. Every page renders (empty database → friendly empty states) ───────────

@pytest.mark.parametrize("name", VIEWS)
def test_every_page_renders_on_empty_db(name):
    at = view(name).run()
    assert not at.exception, [e.value for e in at.exception]


def test_full_app_starts_with_navigation_and_zero_stats():
    at = AppTest.from_file(APP, default_timeout=30).run()
    assert not at.exception
    html = text_of(at)
    assert "A little care can change a life." in html
    assert "Care connects us all." in html
    assert ">0<" in html.replace(" ", "") or "<b>0</b>" in html          # honest zero state, no fake numbers


# ── 2. Donor registration ────────────────────────────────────────────────────

def test_donor_registration_persists_and_shows_ids():
    at = view("donor_registration").run()
    fill_donor(at)
    click(at, "Register as a donor")
    at.run()
    assert not at.exception
    html = text_of(at)
    assert "You&#x27;re registered." in html or "You're registered." in html
    assert "LL-D-" in html
    donors = db.get_donors()
    assert len(donors) == 1 and donors[0]["city"] == "Patna"


def test_donor_validation_blocks_bad_input():
    at = view("donor_registration").run()
    fill_donor(at, name="R", phone="123", city="", consent=False)
    click(at, "Register as a donor")
    at.run()
    html = text_of(at)
    assert "Full name must be" in html and "Mobile number must have 10 digits" in html
    assert "City is required" in html and "consent" in html.lower()
    assert db.get_donors() == []


def test_duplicate_registration_in_new_session_is_handled():
    for _ in range(2):
        at = view("donor_registration").run()
        fill_donor(at)
        click(at, "Register as a donor")
        at.run()
    assert len(db.get_donors()) == 1
    assert "Already registered" in text_of(at)


def test_organ_donor_needs_an_organ():
    at = view("donor_registration").run()
    fill_donor(at)
    by_label(at.selectbox, "Donation type").select("Organ")
    click(at, "Register as a donor")
    at.run()
    assert "Choose at least one organ" in text_of(at)
    assert db.get_donors() == []


def test_availability_update_by_code():
    d = db.add_donor("Ravi Kumar", 30, "Male", "O-", "Blood", [], "Patna", "Bihar", "+91 98765 43210", "")
    at = view("donor_registration").run()
    by_label(at.text_input, "Donor ID").set_value(d["id"])
    by_label(at.text_input, "Access code").set_value(d["access_code"])
    at.radio[0].set_value("Not available right now")
    click(at, "Update my status")
    at.run()
    assert not at.exception and db.get_donors()[0]["available"] is False
    by_label(at.text_input, "Access code").set_value("WRONG-CODE")
    at.radio[0].set_value("Available to donate")
    click(at, "Update my status")
    at.run()
    assert db.get_donors()[0]["available"] is False
    assert "couldn&#x27;t match" in text_of(at) or "couldn't match" in text_of(at)


# ── 3. Requests ──────────────────────────────────────────────────────────────

def fill_request(at, name="Priya Sharma"):
    by_label(at.text_input, "Patient's full name").set_value(name)
    by_label(at.text_input, "Contact number").set_value("91234 56789")
    by_label(at.text_input, "City").set_value("Patna")
    by_label(at.text_input, "Hospital").set_value("AIIMS Patna")
    by_label(at.text_area, "Short medical summary").set_value("Needs transfusion before surgery.")
    at.checkbox[0].check()


def test_request_flow_and_tracking():
    at = view("recipient_request").run()
    fill_request(at)
    click(at, "Post request")
    at.run()
    assert not at.exception
    rows = db.get_recipients()
    assert len(rows) == 1 and rows[0]["status"] == "Open"
    assert "LL-R-" in text_of(at)


def test_request_validation_and_duplicate():
    at = view("recipient_request").run()
    fill_request(at)
    by_label(at.text_area, "Short medical summary").set_value("")
    click(at, "Post request")
    at.run()
    assert "Medical summary are required" in text_of(at) and db.get_recipients() == []
    for _ in range(2):
        at = view("recipient_request").run()
        fill_request(at)
        click(at, "Post request")
        at.run()
    assert len(db.get_recipients()) == 1 and "Possible duplicate" in text_of(at)


def test_open_requests_tab_is_anonymous():
    db.add_recipient("Priya Sharma", 40, "Female", "A+", "Blood", "", "Patna", "Bihar", "AIIMS Patna",
                     "91234 56789", "x@y.com", "Critical (< 24 hrs)", "private diagnosis")
    at = view("recipient_request").run()
    html = text_of(at)
    for secret in ("Priya", "AIIMS", "91234", "private diagnosis", "x@y.com"):
        assert secret not in html
    assert "Patna" in html and "LL-R-" in html


# ── 4. Matching ──────────────────────────────────────────────────────────────

def seed_match_data():
    db.add_donor("Ravi Kumar", 30, "Male", "O-", "Blood", [], "Patna", "Bihar", "+91 98765 43210", "r@example.com", "secret note")
    db.add_donor("Anita Rao", 28, "Female", "A+", "Blood", [], "Delhi", "Delhi", "+91 90000 00001", "")
    return db.add_recipient("Priya Sharma", 40, "Female", "A+", "Blood", "", "Patna", "Bihar", "AIIMS Patna",
                            "91234 56789", "", "Urgent (1–3 days)", "surgery")


def test_matching_results_are_private_and_savable(monkeypatch):
    req = seed_match_data()
    at = view("matching_engine").run()
    assert not at.exception
    html = text_of(at)
    for secret in ("Ravi", "98765", "r@example.com", "secret note", "Anita", "90000", "Priya", "AIIMS"):
        assert secret not in html, secret
    assert "LL-D-" in html
    save = [b for b in at.button if b.label == "Save match"]
    assert len(save) == 2
    save[0].click()
    at.run()
    assert not at.exception
    store = {"_admin_until": time.time() + 600}          # read back as an administrator
    monkeypatch.setattr(auth, "_session", lambda: store)
    ms = db.get_matches()
    assert len(ms) == 1 and ms[0]["recipient_id"] == req["id"]
    assert ms[0]["details"]["blood_score"] in (80.0, 100.0)


def test_matching_filters_and_empty_states():
    seed_match_data()
    at = view("matching_engine").run()
    by_label(at.multiselect, "Donor blood group").set_value(["A+"])
    at.run()
    html = text_of(at)
    assert not at.exception
    assert len([b for b in at.button if b.label == "Save match"]) == 1
    by_label(at.slider, "Minimum score").set_value(100)
    at.run()
    assert "No donors match those filters" in text_of(at)


def test_matching_no_data_shows_guidance():
    at = view("matching_engine").run()
    assert "No open requests yet" in text_of(at)


def test_reverse_matching_needs_donor_id():
    d = db.add_donor("Ravi Kumar", 30, "Male", "O-", "Blood", [], "Patna", "Bihar", "+91 98765 43210", "")
    db.add_recipient("Priya Sharma", 40, "Female", "A+", "Blood", "", "Patna", "Bihar", "AIIMS",
                     "91234 56789", "", "Critical (< 24 hrs)", "x")
    at = view("matching_engine").run()
    at.radio[0].set_value("Find requests for a donor")
    at.run()
    assert "Enter your donor ID" in text_of(at)
    by_label(at.text_input, "Your donor ID").set_value(d["id"])
    at.run()
    assert not at.exception
    assert any(b.label == "Save match" for b in at.button)
    assert "Priya" not in text_of(at)


# ── 5. Admin ─────────────────────────────────────────────────────────────────

def test_admin_page_requires_login_and_leaks_nothing(monkeypatch):
    db.add_donor("Ravi Kumar", 30, "Male", "O-", "Blood", [], "Patna", "Bihar", "+91 98765 43210", "r@example.com")
    monkeypatch.setenv("ADMIN_PASSWORD_HASH", auth.hash_secret("correct horse battery", iterations=1000))
    at = view("admin_dashboard").run()
    html = text_of(at)
    assert "Administrator sign-in" in html
    for secret in ("Ravi", "98765", "r@example.com"):
        assert secret not in html
    assert [w.label for w in at.text_input] == ["Password"]


def test_admin_wrong_and_right_password(monkeypatch):
    monkeypatch.setenv("ADMIN_PASSWORD_HASH", auth.hash_secret("correct horse battery", iterations=1000))
    monkeypatch.setattr(auth.time, "sleep", lambda s: None)
    db.add_donor("Ravi Kumar", 30, "Male", "O-", "Blood", [], "Patna", "Bihar", "+91 98765 43210", "r@example.com")
    at = view("admin_dashboard").run()
    at.text_input[0].set_value("wrong")
    click(at, "Sign in")
    at.run()
    assert "not correct" in text_of(at) and "Ravi" not in text_of(at)
    at.text_input[0].set_value("correct horse battery")
    click(at, "Sign in")
    at.run()
    assert not at.exception, [e.value for e in at.exception]
    assert "Live overview" in text_of(at)
    for section in ["Donors", "Requests", "Matches", "Activity log", "Overview"]:
        at.sidebar.radio[0].set_value(section)
        at.run()
        assert not at.exception, (section, [e.value for e in at.exception])


def test_admin_not_configured_message():
    at = view("admin_dashboard").run()
    assert "Admin access is switched off" in text_of(at)


def test_admin_escapes_html_in_user_content(monkeypatch):
    monkeypatch.setenv("ADMIN_PASSWORD", "pw-pw-pw-pw-pw")
    monkeypatch.setattr(auth.time, "sleep", lambda s: None)
    db.add_recipient("Priya Sharma", 40, "Female", "A+", "Blood", "", "Patna", "Bihar", "<img src=x onerror=alert(1)>",
                     "91234 56789", "", "Stable", "<script>alert(1)</script>")
    at = view("admin_dashboard").run()
    at.text_input[0].set_value("pw-pw-pw-pw-pw")
    click(at, "Sign in")
    at.run()
    at.sidebar.radio[0].set_value("Requests")
    at.run()
    html = text_of(at)
    assert "<script>alert(1)</script>" not in html and "<img src=x" not in html
    assert "&lt;script&gt;" in html


# ── 6. AI assistant ──────────────────────────────────────────────────────────

def test_ai_unavailable_without_key():
    at = view("ai_assistant").run()
    assert not at.exception and "not available right now" in text_of(at)


def test_ai_chat_works_and_recovers_from_errors(monkeypatch):
    from utils import ai_helper
    monkeypatch.setenv("GEMINI_API_KEY", "test-key-not-real")
    calls = {"n": 0}

    def fake(msg, hist):
        calls["n"] += 1
        if calls["n"] == 1:
            raise ai_helper.AIUnavailable("The AI assistant is busy or unavailable right now.")
        return "O- is the universal red-cell donor type."

    monkeypatch.setattr(ai_helper, "chat_with_context", fake)
    at = view("ai_assistant").run()
    at.chat_input[0].set_value("What is O-?").run()
    assert "busy or unavailable" in text_of(at)
    click(at, "Try again")
    at.run()
    assert not at.exception
    assert [m.name for m in at.chat_message] == ["user", "assistant"]
    assert "test-key-not-real" not in text_of(at)


# ── 7. Database outage ───────────────────────────────────────────────────────

def test_app_handles_database_outage(monkeypatch):
    from utils import database
    monkeypatch.setenv("DATABASE_URL", "postgresql://u:p@127.0.0.1:1/none?connect_timeout=1")
    monkeypatch.setenv("DB_POOL_TIMEOUT", "2")
    database.reset_connections()
    at = AppTest.from_file(APP, default_timeout=40).run()
    try:
        assert not at.exception
        assert "can't reach the database" in text_of(at) or "can&#x27;t reach the database" in text_of(at)
    finally:
        database.reset_connections()
