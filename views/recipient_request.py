"""
Page: Request Blood — post a request, track it, browse open needs (anonymised).
All records are stored in the database.
"""

from __future__ import annotations

import uuid

import streamlit as st

from config.constants import (
    ALL_BLOOD_TYPES, DONATION_TYPES, GENDERS, INDIAN_STATES, ORGAN_TYPES, URGENCY_LEVELS,
)
from utils import ai_helper, db, nav, ui, validators as v
from views.donor_registration import _step


def _success_screen(req: dict) -> None:
    ui.notice("ok", "Your request is now visible to the matching engine and our coordinators.", "Request posted.")
    c1, c2 = st.columns(2)
    with c1:
        ui.render(ui.id_box("Request ID", req["id"]))
    with c2:
        ui.render(ui.id_box("Tracking code (private)", req["access_code"]))
    ui.notice("warn", "Save your tracking code now — it is shown only once. With your request ID it lets you check "
                      "the status and close the request. Keep it private.", "Keep this safe.")
    ui.render(f"""<div class="ll-card"><h3 style="margin-top:0">What happens next</h3>
    <p>1. Open <b>Find a Donor</b> to see compatible, available donors for this request.<br>
    2. Save the best matches — a coordinator will contact the donors and you.<br>
    3. Please also contact the treating hospital's blood bank directly. LifeLink works alongside them, not instead.</p></div>""")
    triage = st.session_state.get("request_ai_note")
    if triage:
        with st.expander("AI urgency check"):
            st.write(triage)
            st.caption("An automated second opinion on the urgency level — not a medical assessment.")
    st.write("")
    b1, b2 = st.columns(2)
    with b1:
        if st.button("Find compatible donors", type="primary", use_container_width=True, key="req_next_find"):
            nav.go("matching")
    with b2:
        if st.button("Post another request", use_container_width=True, key="req_again"):
            for k in ("request_done", "request_ai_note"):
                st.session_state.pop(k, None)
            st.rerun()


def _post_tab() -> None:
    if "request_done" in st.session_state:
        _success_screen(st.session_state["request_done"])
        return

    st.session_state.setdefault("request_submit_key", uuid.uuid4().hex)
    ui.emergency_notice()

    with st.form("recipient_form"):
        _step(1, "The patient")
        c1, c2, c3 = st.columns([2, 1, 1])
        name = c1.text_input("Patient's full name *", placeholder="e.g. Priya Sharma", max_chars=80,
                             help="Private — only authorised coordinators can see this.")
        age = c2.number_input("Age *", min_value=0, max_value=120, value=35)
        gender = c3.selectbox("Gender *", GENDERS)
        c4, c5 = st.columns(2)
        phone = c4.text_input("Contact number *", placeholder="+91 98765 43210", max_chars=20,
                              help="A family member or the hospital's blood-bank desk.")
        email = c5.text_input("Contact email (optional)", placeholder="contact@example.com", max_chars=254)

        st.divider()
        _step(2, "What is needed")
        c6, c7 = st.columns(2)
        blood_type = c6.selectbox("Patient's blood group *", ALL_BLOOD_TYPES)
        need_type = c7.selectbox("Type of need *", DONATION_TYPES)
        organ_needed = st.selectbox("Organ required (only if the need is Organ)", ["—"] + ORGAN_TYPES)
        urgency = st.select_slider("How urgent is it? *", options=URGENCY_LEVELS, value=URGENCY_LEVELS[1])
        notes = st.text_area("Short medical summary *", height=110, max_chars=1000,
                             placeholder="Condition, why blood/organ is needed, anything the coordinator should know.")
        st.caption("An AI service may review this summary to suggest whether the urgency level fits. "
                   "Your name and contact details are never sent to it.")

        st.divider()
        _step(3, "Where the patient is")
        c8, c9 = st.columns(2)
        city = c8.text_input("City *", placeholder="e.g. Patna", max_chars=60)
        state = c9.selectbox("State *", INDIAN_STATES, index=INDIAN_STATES.index("Bihar"))
        hospital = st.text_input("Hospital *", placeholder="e.g. AIIMS Patna", max_chars=120,
                                 help="Shown to coordinators only, not on public pages.")

        st.divider()
        _step(4, "Your confirmation")
        consent = st.checkbox("I confirm this request is genuine and I am authorised to share this patient's "
                              "details for donor matching.")
        submitted = st.form_submit_button("Post request", type="primary", use_container_width=True)

    if not submitted:
        return

    name_c, e1 = v.validate_name(name, "Patient's name")
    phone_c, e2 = v.validate_phone(phone, "Contact number", allow_landline=True)
    email_c, e3 = v.validate_email(email)
    city_c, e4 = v.validate_place(city, "City")
    hosp_c, e5 = v.validate_hospital(hospital)
    notes_c, e6 = v.validate_notes(notes, required=True, label="Medical summary")
    errors = [e for e in (e1, e2, e3, e4, e5, e6) if e]
    if need_type == "Organ" and organ_needed == "—":
        errors.append("Choose which organ is required, or switch the type of need to Blood.")
    if not consent:
        errors.append("Please confirm the request is genuine before posting.")
    if errors:
        for e in errors:
            ui.notice("urgent", e)
        return

    try:
        req = db.add_recipient(
            name=name_c, age=int(age), gender=gender, blood_type=blood_type, need_type=need_type,
            organ_needed=organ_needed if need_type == "Organ" else "", city=city_c, state=state,
            hospital=hosp_c, phone=phone_c, email=email_c, urgency=urgency, medical_notes=notes_c,
            submit_key=st.session_state["request_submit_key"],
        )
    except db.DuplicateError as exc:
        if exc.kind == "resubmit":
            ui.notice("info", "This request was already received. Check the confirmation you saw earlier.",
                      "Already submitted.")
        else:
            ui.notice("warn", "There is already an active request for this patient and need. Use “Track a request” "
                              "with your request ID and tracking code, or close it first.", "Possible duplicate.")
        return

    st.session_state["request_submit_key"] = uuid.uuid4().hex
    st.session_state["request_done"] = req
    if ai_helper.ai_available():
        try:
            with st.spinner("Checking the urgency level…"):
                st.session_state["request_ai_note"] = ai_helper.triage_urgency(notes_c, urgency)
        except ai_helper.AIUnavailable:
            st.session_state.pop("request_ai_note", None)
    st.rerun()


def _track_tab() -> None:
    st.markdown("Check the status of a request you posted, or close it once the need has been met.")
    with st.form("track_form"):
        c1, c2 = st.columns(2)
        rid = c1.text_input("Request ID", placeholder="LL-R-XXXXXXXX", max_chars=20)
        code = c2.text_input("Tracking code", placeholder="XXXX-XXXX", type="password", max_chars=12)
        go = st.form_submit_button("Check status", type="primary", use_container_width=True)
    if go:
        if not rid.strip() or not code.strip():
            ui.notice("urgent", "Enter both the request ID and tracking code.")
        else:
            try:
                rec = db.get_my_request(rid, code)
            except PermissionError as exc:
                ui.notice("warn", str(exc), "Locked for now.")
                rec = None
            else:
                if rec is None:
                    ui.notice("urgent", "We couldn't match that request ID and tracking code. Check both and try again.")
            st.session_state["tracked"] = (rid.strip().upper(), code, rec) if rec else None

    tracked = st.session_state.get("tracked")
    if not tracked:
        return
    rid_t, code_t, rec = tracked
    fresh = db.get_my_request(rid_t, code_t) or rec
    st.session_state["tracked"] = (rid_t, code_t, fresh)
    need = fresh["organ_needed"] or fresh["need_type"]
    ui.render(f"""<div class="ll-card"><div style="display:flex;justify-content:space-between;gap:1rem;flex-wrap:wrap">
    <div><h3 style="margin:0">{ui.esc(fresh['id'])}</h3>
    <div class="ll-kv"><span><b>Blood group</b> {ui.esc(fresh['blood_type'])}</span><span><b>Need</b> {ui.esc(need)}</span>
    <span><b>Location</b> {ui.esc(fresh['city'])}, {ui.esc(fresh['state'])}</span>
    <span><b>Posted</b> {ui.fmt_dt(fresh['posted_at'], '%d %b %Y')}</span></div></div>
    <div>{ui.status_pill(fresh['status'])} {ui.urgency_pill(fresh['urgency'])}</div></div>
    <div class="ll-kv" style="margin-top:.8rem"><span><b>Matches saved</b> {fresh['saved_matches']}</span>
    <span><b>Donors contacted</b> {fresh['contacted_matches']}</span></div></div>""")
    if fresh["status"] in ("Open", "In Progress"):
        st.write("")
        c1, c2 = st.columns(2)
        with c1:
            if st.button("Mark as fulfilled", use_container_width=True, key="trk_done"):
                db.set_my_request_status(rid_t, code_t, "Fulfilled")
                st.rerun()
        with c2:
            if st.button("Cancel this request", use_container_width=True, key="trk_cancel"):
                st.session_state["confirm_cancel"] = True
        if st.session_state.get("confirm_cancel"):
            ui.notice("warn", "Cancelling closes the request to donors. This can't be undone.")
            if st.button("Yes, cancel the request", type="primary", key="trk_cancel_yes"):
                db.set_my_request_status(rid_t, code_t, "Cancelled")
                st.session_state.pop("confirm_cancel", None)
                st.rerun()
    else:
        ui.notice("info", f"This request is {fresh['status'].lower()}. No further action is needed.")


def _open_tab() -> None:
    rows = db.get_recipients(open_only=True)
    if not rows:
        ui.empty_state("No open requests right now",
                       "When someone posts a request, it appears here without any personal details.", "drop")
        return
    ui.notice("info", "Requests are anonymous: blood group, need, urgency and city only. Coordinators handle all contact.")
    c1, c2 = st.columns(2)
    f_blood = c1.multiselect("Blood group", ALL_BLOOD_TYPES, key="open_f_blood")
    f_urg = c2.multiselect("Urgency", URGENCY_LEVELS, key="open_f_urg")
    shown = [r for r in rows if (not f_blood or r["blood_type"] in f_blood) and (not f_urg or r["urgency"] in f_urg)]
    st.caption(f"{len(shown)} of {len(rows)} open request{'s' if len(rows) != 1 else ''}, most urgent first.")
    if not shown:
        ui.empty_state("Nothing matches those filters", "Clear a filter to see more requests.", "search")
        return
    for r in shown:
        need = r["organ_needed"] or r["need_type"]
        ui.render(f"""<div class="ll-card" style="margin-bottom:.7rem;height:auto"><div style="display:flex;justify-content:space-between;
        gap:1rem;flex-wrap:wrap;align-items:center"><div><b style="color:var(--head);font-size:1.05rem">{ui.esc(r['blood_type'])} · {ui.esc(need)}</b>
        <div class="ll-kv"><span><b>{ui.esc(r['id'])}</b></span><span>{ui.esc(r['city'])}, {ui.esc(r['state'])}</span>
        <span>Posted {ui.fmt_dt(r['posted_at'], '%d %b')}</span></div></div>
        <div>{ui.urgency_pill(r['urgency'])}</div></div></div>""")


def render() -> None:
    ui.page_header("Request blood", "Tell us what's needed. We'll help the right donors find you.", "drop")
    t1, t2, t3 = st.tabs(["Post a request", "Track a request", "Open requests"])
    with t1:
        _post_tab()
    with t2:
        _track_tab()
    with t3:
        _open_tab()
