"""
Page: Become a Donor — registration, self-service availability, community overview.
Records are written to the database (never to session state).
"""

from __future__ import annotations

import uuid

import streamlit as st

from config.constants import (
    ALL_BLOOD_TYPES, DONATION_TYPES, DONOR_MAX_AGE, DONOR_MIN_AGE, GENDERS, INDIAN_STATES, ORGAN_TYPES,
)
from utils import ai_helper, db, nav, ui, validators as v


def _step(n: int, title: str, hint: str = "") -> None:
    ui.render(f'<div style="display:flex;gap:.7rem;align-items:center;margin:.2rem 0 .6rem">'
              f'<div class="ll-step"><div class="num" style="width:30px;height:30px;font-size:.85rem">{n}</div></div>'
              f'<div><b style="color:var(--head)">{ui.esc(title)}</b>'
              f'{f"<div style=color:var(--muted);font-size:.85rem>{ui.esc(hint)}</div>" if hint else ""}</div></div>')


def _success_screen(donor: dict) -> None:
    ui.notice("ok", f"Thank you for joining LifeLink. You are now part of the donor community.", "You're registered.")
    c1, c2 = st.columns(2)
    with c1:
        ui.render(ui.id_box("Your donor ID", donor["id"]))
    with c2:
        ui.render(ui.id_box("Your private access code", donor["access_code"]))
    ui.notice("warn", "Save your access code now — it is shown only once and we cannot recover it. You need it, with "
                      "your donor ID, to pause or resume your availability.", "Keep this safe.")
    ui.render(f"""
    <div class="ll-card"><h3 style="margin-top:0">What happens next</h3>
    <p>A coordinator may contact you on the phone number you provided when a request matches your blood group and
    location. You can say no at any time. Your name and contact details are never shown in public search results.</p></div>""")

    note = st.session_state.get("donor_ai_note")
    if note:
        with st.expander("AI profile note"):
            st.write(note)
            st.caption("Generated from non-identifying details only. It is not medical advice.")

    st.write("")
    b1, b2 = st.columns(2)
    with b1:
        if st.button("See who needs help", type="primary", use_container_width=True, key="donor_next_find"):
            nav.go("matching")
    with b2:
        if st.button("Register another donor", use_container_width=True, key="donor_again"):
            for k in ("donor_done", "donor_ai_note"):
                st.session_state.pop(k, None)
            st.rerun()


def _register_tab() -> None:
    if "donor_done" in st.session_state:
        _success_screen(st.session_state["donor_done"])
        return

    st.session_state.setdefault("donor_submit_key", uuid.uuid4().hex)
    ui.emergency_notice()

    with st.form("donor_form"):
        _step(1, "About you")
        c1, c2, c3 = st.columns([2, 1, 1])
        name = c1.text_input("Full name *", placeholder="e.g. Ravi Kumar", max_chars=80)
        age = c2.number_input("Age *", min_value=DONOR_MIN_AGE, max_value=DONOR_MAX_AGE, value=25)
        gender = c3.selectbox("Gender *", GENDERS)
        c4, c5 = st.columns(2)
        phone = c4.text_input("Mobile number *", placeholder="+91 98765 43210", max_chars=20,
                              help="Only authorised coordinators can see this.")
        email = c5.text_input("Email (optional)", placeholder="you@example.com", max_chars=254)

        st.divider()
        _step(2, "What you can donate")
        c6, c7 = st.columns(2)
        blood_type = c6.selectbox("Blood group *", ALL_BLOOD_TYPES)
        donation_type = c7.selectbox("Donation type *", DONATION_TYPES)
        organs = st.multiselect("Organs you are willing to donate", ORGAN_TYPES,
                                help="Only needed when the donation type is Organ.")
        notes = st.text_area("Health notes for the coordinator (optional)", height=90, max_chars=1000,
                             placeholder="Recent surgeries, medicines, anything a coordinator should know. "
                                         "Visible to authorised staff only.")

        st.divider()
        _step(3, "Where you are")
        c8, c9 = st.columns(2)
        city = c8.text_input("City *", placeholder="e.g. Patna", max_chars=60)
        state = c9.selectbox("State *", INDIAN_STATES, index=INDIAN_STATES.index("Bihar"))

        st.divider()
        _step(4, "Your consent")
        consent = st.checkbox(
            "I agree to share these details for donor–recipient matching. I understand LifeLink only coordinates, "
            "and that any donation requires a medical evaluation.")
        submitted = st.form_submit_button("Register as a donor", type="primary", use_container_width=True)

    if not submitted:
        return

    name_c, e1 = v.validate_name(name, "Full name")
    phone_c, e2 = v.validate_phone(phone, "Mobile number")
    email_c, e3 = v.validate_email(email)
    city_c, e4 = v.validate_place(city, "City")
    notes_c, e5 = v.validate_notes(notes, label="Health notes")
    errors = [e for e in (e1, e2, e3, e4, e5) if e]
    if donation_type == "Organ" and not organs:
        errors.append("Choose at least one organ, or switch the donation type to Blood.")
    if not consent:
        errors.append("Please tick the consent box so we can register you.")
    if errors:
        for e in errors:
            ui.notice("urgent", e)
        return

    try:
        donor = db.add_donor(
            name=name_c, age=int(age), gender=gender, blood_type=blood_type, donation_type=donation_type,
            organs=organs if donation_type == "Organ" else [], city=city_c, state=state, phone=phone_c,
            email=email_c, medical_notes=notes_c, submit_key=st.session_state["donor_submit_key"],
        )
    except db.DuplicateError as exc:
        if exc.kind == "resubmit":
            ui.notice("info", "This registration was already received. If you saved your donor ID and access code, "
                              "you're all set.", "Already submitted.")
        else:
            ui.notice("warn", "A donor with this mobile number is already registered. If that was you, use "
                              "“Manage my availability” with your donor ID and access code.", "Already registered.")
        return

    st.session_state["donor_submit_key"] = uuid.uuid4().hex   # next form render = a new submission
    st.session_state["donor_done"] = donor
    if ai_helper.ai_available():
        try:
            with st.spinner("Preparing a short profile note…"):
                st.session_state["donor_ai_note"] = ai_helper.analyse_donor_profile({
                    "age": int(age), "gender": gender, "blood_type": blood_type, "donation_type": donation_type,
                    "organs": organs, "medical_notes": notes_c})
        except ai_helper.AIUnavailable:
            st.session_state.pop("donor_ai_note", None)   # optional extra — never block registration
    st.rerun()


def _availability_tab() -> None:
    st.markdown("Need to pause donating, or ready again? Update your status with the details you received "
                "when you registered.")
    with st.form("availability_form"):
        c1, c2 = st.columns(2)
        donor_id = c1.text_input("Donor ID", placeholder="LL-D-XXXXXXXX", max_chars=20)
        code = c2.text_input("Access code", placeholder="XXXX-XXXX", type="password", max_chars=12)
        choice = st.radio("My status", ["Available to donate", "Not available right now"], horizontal=True)
        go = st.form_submit_button("Update my status", type="primary", use_container_width=True)
    if not go:
        return
    if not donor_id.strip() or not code.strip():
        ui.notice("urgent", "Enter both your donor ID and access code.")
        return
    try:
        ok = db.set_my_availability(donor_id, code, choice.startswith("Available"))
    except PermissionError as exc:
        ui.notice("warn", str(exc), "Locked for now.")
        return
    if ok:
        ui.notice("ok", "Your availability is updated: " + choice.lower() + ".", "Saved.")
    else:
        ui.notice("urgent", "We couldn't match that donor ID and access code. Check both and try again.")


def _community_tab() -> None:
    counts = db.donor_blood_counts()
    total = sum(counts.values())
    if total == 0:
        ui.empty_state("No available donors yet",
                       "Be the first to register — every blood group is needed.", "users")
        return
    st.markdown(f"**{total}** donor{'s' if total != 1 else ''} currently available across all blood groups.")
    cells = "".join(f'<div class="cell"><b>{bt}</b><span>{n} available</span></div>' for bt, n in counts.items())
    ui.render(f'<div class="ll-bgrid">{cells}</div>')
    st.caption("Anonymous totals only. Individual donors are never listed publicly.")


def render() -> None:
    ui.page_header("Become a donor", "Two minutes to register. A lifetime of difference for someone else.", "userplus")
    t1, t2, t3 = st.tabs(["Register", "Manage my availability", "Community"])
    with t1:
        _register_tab()
    with t2:
        _availability_tab()
    with t3:
        _community_tab()
