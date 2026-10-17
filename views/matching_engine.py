"""
Page: Find a Donor — the original matching engine behind a calmer interface.

The scoring algorithm (utils/matching.py) and its weights are untouched. This page
only fetches records, filters/sorts the scored results and renders them.
Search results are public-safe: donor ID, blood group, city/state, availability,
donation type and score — never names, phone numbers or emails.
"""

from __future__ import annotations

import streamlit as st

from config.constants import ALL_BLOOD_TYPES, URGENCY_LEVELS, URGENCY_WEIGHT
from utils import ai_helper, auth, db, nav, ui
from utils.matching import find_recipients_for_donor, match_donors_to_recipient

_SCOPES = ["Anywhere", "Same state", "Same city"]


def _same(a: str, b: str) -> bool:
    return (a or "").strip().lower() == (b or "").strip().lower() and bool((a or "").strip())


def _in_scope(scope: str, donor: dict, recipient: dict) -> bool:
    if scope == "Same city":
        return _same(donor["city"], recipient["city"]) and _same(donor["state"], recipient["state"])
    if scope == "Same state":
        return _same(donor["state"], recipient["state"])
    return True


def _factor_bars(m: dict) -> str:
    rows = [("Blood compatibility", m["blood_score"], "40%", ""),
            ("Location", m["location_score"], "30%", "sage"),
            ("Urgency", m["urgency_score"], "20%", "teal"),
            ("Availability", m["availability_score"], "10%", "sage")]
    return "".join(
        f'<div style="display:flex;justify-content:space-between;font-size:.88rem"><span>{ui.esc(n)} '
        f'<span style="color:var(--muted)">(weight {w})</span></span><b>{s:g}/100</b></div>{ui.progress_bar(s, tone)}'
        for n, s, w, tone in rows)


def _details(m: dict) -> dict:
    return {"reasons": m["reasons"], "blood_score": m["blood_score"], "location_score": m["location_score"],
            "urgency_score": m["urgency_score"], "availability_score": m["availability_score"],
            "total_score": m["total_score"]}


def _save(donor_id: str, request_id: str, m: dict) -> None:
    try:
        rec = db.save_match(donor_id, request_id, m["total_score"], _details(m))
    except (ValueError, db.NotFoundError) as exc:
        st.toast(str(exc), icon=":material/error:")
        return
    if rec["created"]:
        st.toast("Match saved. A coordinator will follow up.", icon=":material/check_circle:")
    else:
        st.toast("This pair is already saved.", icon=":material/info:")


def _explain_block(m: dict, key: str) -> None:
    """Optional AI explanation (existing Gemini feature) with retry."""
    if not ai_helper.ai_available():
        return
    ck = f"ai_expl_{key}"
    if st.button("Explain this match", key=f"btn_{ck}"):
        try:
            with st.spinner("Writing an explanation…"):
                st.session_state[ck] = ai_helper.explain_match(m)
        except ai_helper.AIUnavailable as exc:
            st.session_state.pop(ck, None)
            ui.notice("warn", f"{exc} Press the button again to retry.")
    if st.session_state.get(ck):
        ui.notice("info", st.session_state[ck])


# ── Direction 1: donors for a request ────────────────────────────────────────

def _donors_for_request() -> None:
    requests = db.get_recipients(open_only=True)
    if not requests:
        ui.empty_state("No open requests yet", "Post a request first, then come back to see compatible donors.", "drop")
        if st.button("Post a request", type="primary", key="m_goto_req"):
            nav.go("request")
        return
    donors = db.get_donors(available_only=True)
    if not donors:
        ui.empty_state("No available donors yet",
                       "Nobody has registered as available. Invite friends and family to join as donors.", "users")
        if st.button("Become a donor", type="primary", key="m_goto_donor"):
            nav.go("donor")
        return

    labels = {f"{r['id']} · {r['blood_type']} · {r['organ_needed'] or r['need_type']} · "
              f"{r['city']}, {r['state']} · {r['urgency'].split(' (')[0]}": r for r in requests}
    pick = st.selectbox("Choose a request", list(labels), key="m_req_pick")
    req = labels[pick]
    ui.render(f"""<div class="ll-card ivory" style="height:auto;margin:.4rem 0 1rem"><div style="display:flex;
    justify-content:space-between;gap:1rem;flex-wrap:wrap;align-items:center"><div>
    <b style="color:var(--head)">{ui.esc(req['id'])}</b>
    <div class="ll-kv"><span><b>Needs</b> {ui.esc(req['blood_type'])} {ui.esc(req['organ_needed'] or req['need_type'])}</span>
    <span><b>Location</b> {ui.esc(req['city'])}, {ui.esc(req['state'])}</span></div></div>
    <div>{ui.urgency_pill(req['urgency'])}</div></div></div>""")

    with st.expander("Refine results", expanded=True):
        c1, c2, c3 = st.columns(3)
        f_blood = c1.multiselect("Donor blood group", ALL_BLOOD_TYPES, key="m1_blood")
        scope = c2.selectbox("Location", _SCOPES, key="m1_scope")
        min_score = c3.slider("Minimum score", 0, 100, 0, key="m1_min")
        c4, c5, c6 = st.columns(3)
        query = c4.text_input("Search donor ID or city", key="m1_q", placeholder="e.g. Patna")
        sort = c5.selectbox("Sort by", ["Best match score", "Closest location first"], key="m1_sort")
        top_n = c6.slider("Show up to", 3, 20, 5, key="m1_top")

    # Score everyone with the existing algorithm, then filter/sort the scored list.
    scored = match_donors_to_recipient(req, donors, top_n=max(len(donors), 1))
    out = [m for m in scored
           if m["total_score"] >= min_score
           and (not f_blood or m["donor"]["blood_type"] in f_blood)
           and _in_scope(scope, m["donor"], req)
           and (not query.strip() or query.strip().lower() in m["donor"]["id"].lower()
                or query.strip().lower() in m["donor"]["city"].lower())]
    if sort == "Closest location first":
        out.sort(key=lambda m: (m["location_score"], m["total_score"]), reverse=True)
    out = out[:top_n]

    if not scored:
        ui.empty_state("No compatible donors for this request yet",
                       "No available donor currently matches this blood group and need. "
                       "Share LifeLink so more donors can join.", "search")
    elif not out:
        ui.empty_state("No donors match those filters", "Loosen the filters above to see more compatible donors.", "search")
    else:
        st.markdown(f"**{len(out)}** compatible donor{'s' if len(out) != 1 else ''}"
                    f" (of {len(scored)} compatible in total)")
        ui.medical_disclaimer()

    for i, m in enumerate(out, 1):
        d = m["donor"]
        with st.container(border=True):
            ui.render('<span class="ll-resultcard"></span>')
            a, b, c = st.columns([3.2, 1.6, 1.2], vertical_alignment="center")
            with a:
                what = ", ".join(d["organs"]) if d["organs"] else d["donation_type"]
                ui.render(f"""<b style="color:var(--head);font-size:1.05rem">#{i} · {ui.esc(d['id'])}</b>
                <div style="margin:.35rem 0">{ui.pill(d['blood_type'], 'info')} {ui.pill('Available', 'ok')}
                {ui.pill(what, 'neutral')}</div>
                <div class="ll-kv"><span>{ui.icon('pin', 15)} {ui.esc(d['city'])}, {ui.esc(d['state'])}</span></div>""")
            with b:
                ui.render(f'<div class="ll-score">{m["total_score"]:g}<small> / 100</small></div>'
                          f'{ui.progress_bar(m["total_score"])}{ui.score_pill(m["total_score"])}')
            with c:
                st.button("Save match", key=f"save1_{d['id']}_{req['id']}", type="primary", use_container_width=True,
                          on_click=_save, args=(d["id"], req["id"], m))
            with st.expander("Why this match"):
                ui.render(_factor_bars(m))
                st.markdown("**Matching factors**")
                for r in m["reasons"]:
                    st.markdown(f"- {r}")
                _explain_block(m, f"{d['id']}_{req['id']}")

    if scored and ai_helper.ai_available():
        st.write("")
        if st.button("Suggest next steps", key="m1_next"):
            try:
                with st.spinner("Thinking through next steps…"):
                    st.session_state["m1_next_txt"] = (req["id"], ai_helper.suggest_next_steps(req, scored[0]))
            except ai_helper.AIUnavailable as exc:
                ui.notice("warn", f"{exc} Press the button again to retry.")
        nxt = st.session_state.get("m1_next_txt")
        if nxt and nxt[0] == req["id"]:
            ui.notice("info", nxt[1], "Suggested next steps:")


# ── Direction 2: requests for a donor ────────────────────────────────────────

def _requests_for_donor() -> None:
    is_admin = auth.is_admin()
    donor = None
    if is_admin:
        donors = db.get_donors(include_private=True)
        if not donors:
            ui.empty_state("No donors yet", "Register donors first.", "users")
            return
        opts = {f"{d['id']} · {d['blood_type']} · {d['city']} · {d['name']}": d for d in donors}
        donor = opts[st.selectbox("Choose a donor", list(opts), key="m2_pick")]
    else:
        did = st.text_input("Your donor ID", placeholder="LL-D-XXXXXXXX", key="m2_id", max_chars=20)
        if not did.strip():
            ui.empty_state("Enter your donor ID", "You received it when you registered. We'll show open requests "
                                                  "you could help with.", "userplus")
            return
        donor = db.get_donor_by_id(did)
        if not donor:
            ui.notice("urgent", "We couldn't find that donor ID. Check it and try again.")
            return

    if not donor["available"]:
        ui.notice("warn", "This donor is marked as not available, so no requests are shown. "
                          "Update your status under Become a donor → Manage my availability.")
        return
    requests = db.get_recipients(open_only=True)
    if not requests:
        ui.empty_state("No open requests right now", "Thank you for being ready. We'll have a request for you soon.", "drop")
        return

    with st.expander("Refine results", expanded=True):
        c1, c2, c3 = st.columns(3)
        f_urg = c1.multiselect("Urgency", URGENCY_LEVELS, key="m2_urg")
        scope = c2.selectbox("Location", _SCOPES, key="m2_scope")
        min_score = c3.slider("Minimum score", 0, 100, 0, key="m2_min")
        c4, c5 = st.columns(2)
        sort = c4.selectbox("Sort by", ["Best match score", "Most urgent first", "Closest location first"], key="m2_sort")
        top_n = c5.slider("Show up to", 3, 20, 5, key="m2_top")

    scored = find_recipients_for_donor(donor, requests, top_n=max(len(requests), 1))
    out = [m for m in scored if m["total_score"] >= min_score
           and (not f_urg or m["recipient"]["urgency"] in f_urg) and _in_scope(scope, donor, m["recipient"])]
    if sort == "Most urgent first":
        out.sort(key=lambda m: (URGENCY_WEIGHT.get(m["recipient"]["urgency"], 0), m["total_score"]), reverse=True)
    elif sort == "Closest location first":
        out.sort(key=lambda m: (m["location_score"], m["total_score"]), reverse=True)
    out = out[:top_n]

    if not scored:
        ui.empty_state("No open request fits this donor right now",
                       "Requests appear here when their blood group and need are compatible with yours.", "search")
        return
    if not out:
        ui.empty_state("No requests match those filters", "Loosen the filters above to see more.", "search")
        return
    st.markdown(f"**{len(out)}** request{'s' if len(out) != 1 else ''} you could help with")
    ui.medical_disclaimer()
    for i, m in enumerate(out, 1):
        r = m["recipient"]
        with st.container(border=True):
            ui.render('<span class="ll-resultcard"></span>')
            a, b, c = st.columns([3.2, 1.6, 1.2], vertical_alignment="center")
            with a:
                ui.render(f"""<b style="color:var(--head);font-size:1.05rem">#{i} · {ui.esc(r['id'])}</b>
                <div style="margin:.35rem 0">{ui.pill(r['blood_type'], 'info')} {ui.urgency_pill(r['urgency'])}
                {ui.pill(r['organ_needed'] or r['need_type'], 'neutral')}</div>
                <div class="ll-kv"><span>{ui.icon('pin', 15)} {ui.esc(r['city'])}, {ui.esc(r['state'])}</span></div>""")
            with b:
                ui.render(f'<div class="ll-score">{m["total_score"]:g}<small> / 100</small></div>'
                          f'{ui.progress_bar(m["total_score"])}{ui.score_pill(m["total_score"])}')
            with c:
                st.button("Save match", key=f"save2_{donor['id']}_{r['id']}", type="primary",
                          use_container_width=True, on_click=_save, args=(donor["id"], r["id"], m))
            with st.expander("Why this match"):
                ui.render(_factor_bars(m))
                st.markdown("**Matching factors**")
                for reason in m["reasons"]:
                    st.markdown(f"- {reason}")


def render() -> None:
    ui.page_header("Find a donor", "Compatibility-ranked matches, shown with privacy in mind.", "search")
    direction = st.radio("What would you like to do?",
                         ["Find donors for a request", "Find requests for a donor"], horizontal=True, key="m_dir")
    st.write("")
    if direction == "Find donors for a request":
        _donors_for_request()
    else:
        _requests_for_donor()
