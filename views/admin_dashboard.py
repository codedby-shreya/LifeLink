"""
Page: Admin Dashboard — protected by real authentication.

Nothing on this page is loaded until an administrator has signed in, and every
data function it calls re-checks the admin session on the server
(utils.db → auth.require_admin), so hiding the page is not the only protection.
"""

from __future__ import annotations

import datetime as dt

import pandas as pd
import plotly.graph_objects as go
import streamlit as st

from config.constants import (
    ADMIN_IDLE_TIMEOUT_MINUTES, ALL_BLOOD_TYPES, MATCH_STATUSES, REQUEST_STATUSES, URGENCY_LEVELS,
)
from utils import auth, database, db, ui

OCEAN, SAGE, TEAL, AMBER, CORAL = "#2878B8", "#527C67", "#75B9B4", "#E3B341", "#C96B62"
_SECTIONS = ["Overview", "Donors", "Requests", "Matches", "Activity log"]
_URG_COLORS = {"Critical (< 24 hrs)": CORAL, "Urgent (1–3 days)": AMBER,
               "Moderate (within a week)": TEAL, "Stable": SAGE}


# ── Sign-in ──────────────────────────────────────────────────────────────────

def _login() -> None:
    ui.page_header("Admin dashboard", "Sign in to manage donors, requests and matches.", "lock")
    if not auth.admin_configured():
        ui.notice("warn", "No administrator password has been set for this deployment. Add ADMIN_PASSWORD_HASH to the "
                          "app's secrets (see README → Authentication) and reload.", "Admin access is switched off.")
        return
    _, mid, _ = st.columns([1, 1.4, 1])
    with mid:
        with st.form("admin_login"):
            st.markdown("### Administrator sign-in")
            email = ""
            if auth.admin_email_required():
                email = st.text_input("Admin email", placeholder="you@example.com", max_chars=254)
            pw = st.text_input("Password", type="password", max_chars=200)
            go_ = st.form_submit_button("Sign in", type="primary", use_container_width=True)
        if go_:
            ok, msg = auth.admin_login(pw, email)
            if ok:
                st.rerun()
            ui.notice("urgent", msg)
        st.caption(f"Sessions end after {ADMIN_IDLE_TIMEOUT_MINUTES} minutes without activity.")


# ── Helpers ──────────────────────────────────────────────────────────────────

def _period() -> tuple[pd.Timestamp | None, pd.Timestamp | None]:
    c1, c2 = st.columns([1, 2])
    choice = c1.selectbox("Period", ["All time", "Last 7 days", "Last 30 days", "Last 90 days", "Custom range"],
                          key="adm_period")
    now = pd.Timestamp.now(tz="UTC")
    if choice == "All time":
        return None, None
    if choice == "Custom range":
        rng = c2.date_input("Dates", value=(now.date() - dt.timedelta(days=30), now.date()), key="adm_range")
        if isinstance(rng, tuple) and len(rng) == 2:
            return (pd.Timestamp(rng[0], tz="UTC"), pd.Timestamp(rng[1], tz="UTC") + pd.Timedelta(days=1))
        return None, None
    days = {"Last 7 days": 7, "Last 30 days": 30, "Last 90 days": 90}[choice]
    return now - pd.Timedelta(days=days), now + pd.Timedelta(minutes=1)


def _in_period(df: pd.DataFrame, col: str, start, end) -> pd.DataFrame:
    if df.empty or start is None:
        return df
    ts = pd.to_datetime(df[col], utc=True)
    return df[(ts >= start) & (ts < end)]


def _ist(df: pd.DataFrame, cols: list[str]) -> pd.DataFrame:
    out = df.copy()
    for c in cols:
        if c in out.columns:
            out[c] = pd.to_datetime(out[c], utc=True).dt.tz_convert("Asia/Kolkata").dt.strftime("%d %b %Y %H:%M")
    return out


def _style(fig: go.Figure, height: int = 320) -> go.Figure:
    fig.update_layout(height=height, margin=dict(t=30, b=30, l=10, r=10), paper_bgcolor="rgba(0,0,0,0)",
                      plot_bgcolor="rgba(0,0,0,0)", font=dict(family="Inter, Segoe UI, Arial", color="#475569"),
                      legend=dict(orientation="h", y=-0.2), colorway=[OCEAN, SAGE, TEAL, AMBER, CORAL])
    fig.update_xaxes(gridcolor="#E3EAE3", zeroline=False)
    fig.update_yaxes(gridcolor="#E3EAE3", zeroline=False, rangemode="tozero", tickformat="d")
    return fig


_PLOT_CONFIG = {"displayModeBar": False}


def _show(fig: go.Figure) -> None:
    st.plotly_chart(_style(fig), use_container_width=True, config=_PLOT_CONFIG)


def _chart_card(title: str) -> None:
    st.markdown(f"**{title}**")


def _confirm_delete(kind: str, public_id: str, label: str) -> None:
    st.markdown("**Delete permanently**")
    ok = st.checkbox(f"I understand this permanently deletes {label} and anything linked to it. This cannot be undone.",
                     key=f"del_ok_{kind}_{public_id}")
    if st.button(f"Delete {kind}", key=f"del_btn_{kind}_{public_id}", disabled=not ok):
        db.delete_record(kind, public_id)
        st.toast(f"{kind.capitalize()} {public_id} deleted.", icon=":material/delete:")
        st.rerun()


# ── Sections ─────────────────────────────────────────────────────────────────

def _overview(donors: pd.DataFrame, reqs: pd.DataFrame, matches: pd.DataFrame) -> None:
    start, end = _period()
    d, r, m = (_in_period(donors, "registered_at", start, end), _in_period(reqs, "posted_at", start, end),
               _in_period(matches, "Matched At", start, end))
    open_r = int((r["status"] == "Open").sum()) if not r.empty else 0
    critical = int(((r["status"] == "Open") & r["urgency"].str.startswith("Critical")).sum()) if not r.empty else 0
    ui.stat_cards([("Donors registered", len(d), "users", "blue"), ("Requests posted", len(r), "drop", "sage"),
                   ("Matches saved", len(m), "link", "blue"), ("Critical & open", critical, "alert", "sage")])
    st.write("")
    done = int((m["Status"] == "Completed").sum()) if not m.empty else 0
    avail = int(d["available"].sum()) if not d.empty else 0
    ful = int((r["status"] == "Fulfilled").sum()) if not r.empty else 0
    ui.stat_cards([("Donors available", avail, "check", "sage"), ("Open requests", open_r, "clock", "blue"),
                   ("Matches completed", done, "heart", "sage"), ("Requests fulfilled", ful, "activity", "blue")])
    st.write("")
    if d.empty and r.empty and m.empty:
        ui.empty_state("No activity in this period", "Charts appear as soon as donors, requests or matches are recorded.", "chart")
        return

    c1, c2 = st.columns(2, gap="large")
    with c1:
        _chart_card("Blood group distribution")
        dc = d["blood_type"].value_counts() if not d.empty else pd.Series(dtype=int)
        rc = r["blood_type"].value_counts() if not r.empty else pd.Series(dtype=int)
        fig = go.Figure([go.Bar(name="Donors", x=ALL_BLOOD_TYPES, y=[int(dc.get(b, 0)) for b in ALL_BLOOD_TYPES], marker_color=OCEAN),
                         go.Bar(name="Requests", x=ALL_BLOOD_TYPES, y=[int(rc.get(b, 0)) for b in ALL_BLOOD_TYPES], marker_color=SAGE)])
        fig.update_layout(barmode="group")
        _show(fig)
    with c2:
        _chart_card("Requests by urgency")
        if r.empty:
            ui.empty_state("No requests yet", "", "drop")
        else:
            uc = r["urgency"].value_counts()
            fig = go.Figure(go.Bar(x=[u for u in URGENCY_LEVELS if u in uc], y=[int(uc[u]) for u in URGENCY_LEVELS if u in uc],
                                   marker_color=[_URG_COLORS[u] for u in URGENCY_LEVELS if u in uc]))
            _show(fig)

    c3, c4 = st.columns(2, gap="large")
    with c3:
        _chart_card("Requests and matches over time")
        series = []
        if not r.empty:
            series.append(("Requests", pd.to_datetime(r["posted_at"], utc=True).dt.tz_convert("Asia/Kolkata").dt.date, OCEAN))
        if not m.empty:
            series.append(("Matches", pd.to_datetime(m["Matched At"], utc=True).dt.tz_convert("Asia/Kolkata").dt.date, SAGE))
        if series:
            fig = go.Figure()
            for name, days, colour in series:
                counts = days.value_counts().sort_index()
                fig.add_trace(go.Scatter(x=[d.strftime("%d %b") for d in counts.index], y=counts.values.tolist(), name=name, mode="lines+markers",
                                         line=dict(color=colour, width=3)))
            fig.update_xaxes(type="category")
            _show(fig)
        else:
            ui.empty_state("No trend yet", "", "chart")
    with c4:
        _chart_card("Match status")
        if m.empty:
            ui.empty_state("No matches saved yet", "", "link")
        else:
            sc = m["Status"].value_counts()
            fig = go.Figure(go.Pie(labels=sc.index.tolist(), values=sc.values.tolist(), hole=0.55,
                                   marker=dict(colors=[OCEAN, SAGE, TEAL, AMBER, "#9AA9A0"])))
            _show(fig)

    c5, c6 = st.columns(2, gap="large")
    with c5:
        _chart_card("Recent requests")
        if r.empty:
            ui.empty_state("No requests in this period", "", "drop")
        else:
            show = _ist(r.sort_values("posted_at", ascending=False).head(8), ["posted_at"])
            st.dataframe(show[["id", "blood_type", "urgency", "status", "city", "posted_at"]], hide_index=True, use_container_width=True)
    with c6:
        _chart_card("Recent match activity")
        if m.empty:
            ui.empty_state("No matches in this period", "", "link")
        else:
            show = _ist(m.sort_values("Matched At", ascending=False).head(8), ["Matched At"])
            st.dataframe(show[["Match ID", "Donor ID", "Request ID", "Score", "Status", "Matched At"]], hide_index=True, use_container_width=True)


def _donors(df: pd.DataFrame) -> None:
    if df.empty:
        ui.empty_state("No donors yet", "Donors appear here as soon as they register.", "users")
        return
    c1, c2, c3, c4 = st.columns([2, 1, 1, 1])
    q = c1.text_input("Search", placeholder="ID, name, city or phone", key="ad_q")
    f_blood = c2.multiselect("Blood group", ALL_BLOOD_TYPES, key="ad_b")
    f_avail = c3.selectbox("Availability", ["All", "Available", "Unavailable"], key="ad_a")
    sort = c4.selectbox("Sort", ["Newest first", "Oldest first", "Name A–Z", "Blood group"], key="ad_s")
    f = df
    if q.strip():
        s = q.strip().lower()
        f = f[f.apply(lambda row: s in f"{row['id']} {row['name']} {row['city']} {row['phone']}".lower(), axis=1)]
    if f_blood:
        f = f[f["blood_type"].isin(f_blood)]
    if f_avail != "All":
        f = f[f["available"] == (f_avail == "Available")]
    f = {"Newest first": f.sort_values("registered_at", ascending=False), "Oldest first": f.sort_values("registered_at"),
         "Name A–Z": f.sort_values("name", key=lambda s: s.str.lower()), "Blood group": f.sort_values("blood_type")}[sort]
    st.caption(f"{len(f)} of {len(df)} donors")
    cols = ["id", "name", "age", "gender", "blood_type", "donation_type", "organs", "city", "state", "phone", "email", "available", "registered_at"]
    st.dataframe(_ist(f, ["registered_at"])[cols], hide_index=True, use_container_width=True)
    if f.empty:
        return
    st.markdown("#### Manage a donor")
    pick = st.selectbox("Donor", f["id"].tolist(), format_func=lambda i: f"{i} · {f.set_index('id').loc[i, 'name']}", key="ad_pick")
    row = f.set_index("id").loc[pick]
    ui.render(f"""<div class="ll-card" style="height:auto"><b style="color:var(--head)">{ui.esc(row['name'])}</b>
    <div class="ll-kv"><span><b>Blood</b> {ui.esc(row['blood_type'])}</span><span><b>Phone</b> {ui.esc(row['phone'])}</span>
    <span><b>Email</b> {ui.esc(row['email'] or '—')}</span><span><b>City</b> {ui.esc(row['city'])}, {ui.esc(row['state'])}</span></div>
    <div class="ll-kv"><span><b>Notes</b> {ui.esc(row['medical_notes'] or '—')}</span></div></div>""")
    a, b = st.columns([2, 1])
    new_av = a.toggle("Available to donate", value=bool(row["available"]), key=f"ad_av_{pick}")
    if b.button("Save availability", key=f"ad_avbtn_{pick}", use_container_width=True) and new_av != bool(row["available"]):
        db.update_donor_availability(pick, new_av)
        st.rerun()
    with st.expander("Delete this donor"):
        _confirm_delete("donor", pick, f"donor {pick}")


def _requests(df: pd.DataFrame) -> None:
    if df.empty:
        ui.empty_state("No requests yet", "Requests appear here as soon as they are posted.", "drop")
        return
    c1, c2, c3, c4 = st.columns([2, 1, 1, 1])
    q = c1.text_input("Search", placeholder="ID, patient, hospital or city", key="ar_q")
    f_status = c2.multiselect("Status", REQUEST_STATUSES, key="ar_st")
    f_urg = c3.multiselect("Urgency", URGENCY_LEVELS, key="ar_u")
    sort = c4.selectbox("Sort", ["Newest first", "Most urgent first", "Blood group"], key="ar_s")
    f = df
    if q.strip():
        s = q.strip().lower()
        f = f[f.apply(lambda row: s in f"{row['id']} {row['name']} {row['hospital']} {row['city']}".lower(), axis=1)]
    if f_status:
        f = f[f["status"].isin(f_status)]
    if f_urg:
        f = f[f["urgency"].isin(f_urg)]
    from config.constants import URGENCY_WEIGHT
    f = {"Newest first": f.sort_values("posted_at", ascending=False),
         "Most urgent first": f.assign(_w=f["urgency"].map(URGENCY_WEIGHT)).sort_values(["_w", "posted_at"], ascending=False).drop(columns="_w"),
         "Blood group": f.sort_values("blood_type")}[sort]
    st.caption(f"{len(f)} of {len(df)} requests")
    cols = ["id", "name", "age", "blood_type", "need_type", "organ_needed", "urgency", "status", "hospital", "city", "state", "phone", "posted_at"]
    st.dataframe(_ist(f, ["posted_at"])[cols], hide_index=True, use_container_width=True)
    if f.empty:
        return
    st.markdown("#### Manage a request")
    idx = f.set_index("id")
    pick = st.selectbox("Request", f["id"].tolist(), format_func=lambda i: f"{i} · {idx.loc[i, 'blood_type']} · {idx.loc[i, 'status']}", key="ar_pick")
    row = idx.loc[pick]
    ui.render(f"""<div class="ll-card" style="height:auto"><div style="display:flex;justify-content:space-between;gap:1rem;flex-wrap:wrap">
    <b style="color:var(--head)">{ui.esc(row['name'])}, {int(row['age'])}</b><div>{ui.status_pill(row['status'])} {ui.urgency_pill(row['urgency'])}</div></div>
    <div class="ll-kv"><span><b>Needs</b> {ui.esc(row['blood_type'])} {ui.esc(row['organ_needed'] or row['need_type'])}</span>
    <span><b>Hospital</b> {ui.esc(row['hospital'])}</span><span><b>Phone</b> {ui.esc(row['phone'])}</span>
    <span><b>Email</b> {ui.esc(row['email'] or '—')}</span></div>
    <div class="ll-kv"><span><b>Summary</b> {ui.esc(row['medical_notes'])}</span></div></div>""")
    a, b = st.columns([2, 1], vertical_alignment="bottom")
    new = a.selectbox("Status", REQUEST_STATUSES, index=REQUEST_STATUSES.index(row["status"]), key=f"ar_ns_{pick}")
    if b.button("Update status", key=f"ar_btn_{pick}", type="primary", use_container_width=True) and new != row["status"]:
        db.update_recipient_status(pick, new)
        st.rerun()
    with st.expander("Delete this request"):
        _confirm_delete("request", pick, f"request {pick}")


def _matches(raw: list[dict]) -> None:
    if not raw:
        ui.empty_state("No matches saved yet", "Saved matches from the Find a Donor page appear here for coordination.", "link")
        return
    c1, c2, c3 = st.columns([2, 1, 1])
    q = c1.text_input("Search", placeholder="match, donor or request ID", key="am_q")
    f_status = c2.multiselect("Status", MATCH_STATUSES, key="am_st")
    sort = c3.selectbox("Sort", ["Newest first", "Highest score"], key="am_s")
    f = [m for m in raw if (not f_status or m["status"] in f_status)
         and (not q.strip() or q.strip().lower() in f"{m['id']} {m['donor_id']} {m['recipient_id']}".lower())]
    f.sort(key=(lambda m: m["matched_at"]) if sort == "Newest first" else (lambda m: m["score"]), reverse=True)
    st.caption(f"{len(f)} of {len(raw)} matches")
    table = pd.DataFrame([{"Match": m["id"], "Donor": m["donor_id"], "Request": m["recipient_id"], "Score": m["score"],
                           "Status": m["status"], "Urgency": m["urgency"], "Matched": m["matched_at"]} for m in f])
    if not table.empty:
        st.dataframe(_ist(table, ["Matched"]), hide_index=True, use_container_width=True)
    if not f:
        ui.empty_state("No matches fit those filters", "", "search")
        return
    st.markdown("#### Coordinate a match")
    by_id = {m["id"]: m for m in f}
    pick = st.selectbox("Match", list(by_id), format_func=lambda i: f"{i} · score {by_id[i]['score']:g} · {by_id[i]['status']}", key="am_pick")
    m = by_id[pick]
    ui.render(f"""<div class="ll-grid c2"><div class="ll-card"><h3 style="margin-top:0">Donor {ui.esc(m['donor_id'])}</h3>
    <div class="ll-kv"><span><b>Name</b> {ui.esc(m['donor_name'])}</span><span><b>Blood</b> {ui.esc(m['donor_blood'])}</span></div>
    <div class="ll-kv"><span><b>Phone</b> {ui.esc(m['donor_phone'])}</span><span><b>Email</b> {ui.esc(m['donor_email'] or '—')}</span></div>
    <div class="ll-kv"><span><b>Location</b> {ui.esc(m['donor_city'])}, {ui.esc(m['donor_state'])}</span></div></div>
    <div class="ll-card"><h3 style="margin-top:0">Request {ui.esc(m['recipient_id'])}</h3>
    <div class="ll-kv"><span><b>Patient</b> {ui.esc(m['recipient_name'])}</span><span><b>Blood</b> {ui.esc(m['recipient_blood'])}</span></div>
    <div class="ll-kv"><span><b>Phone</b> {ui.esc(m['recipient_phone'])}</span><span><b>Hospital</b> {ui.esc(m['recipient_hospital'])}</span></div>
    <div class="ll-kv"><span>{ui.urgency_pill(m['urgency'])}</span><span>{ui.status_pill(m['status'])}</span></div></div></div>""")
    with st.expander("Scoring breakdown"):
        d = m["details"]
        st.write({k: d.get(k) for k in ("total_score", "blood_score", "location_score", "urgency_score", "availability_score")})
        for reason in d.get("reasons", []):
            st.markdown(f"- {reason}")
    a, b = st.columns([2, 1], vertical_alignment="bottom")
    new = a.selectbox("Match status", MATCH_STATUSES, index=MATCH_STATUSES.index(m["status"]), key=f"am_ns_{pick}")
    if b.button("Update status", key=f"am_btn_{pick}", type="primary", use_container_width=True) and new != m["status"]:
        db.update_match_status(pick, new)
        st.rerun()
    with st.expander("Delete this match"):
        _confirm_delete("match", pick, f"match {pick}")


def _activity() -> None:
    rows = db.get_audit_log(200)
    if not rows:
        ui.empty_state("No administrator actions yet", "Status changes and deletions are recorded here.", "file")
        return
    df = pd.DataFrame(rows)
    st.dataframe(_ist(df, ["at"]).rename(columns={"at": "When"}), hide_index=True, use_container_width=True)


# ── Entry point ──────────────────────────────────────────────────────────────

def render() -> None:
    if not auth.is_admin():
        _login()
        return

    with st.sidebar:
        st.divider()
        st.markdown("**Admin**")
        section = st.radio("Section", _SECTIONS, key="admin_section", label_visibility="collapsed")
        if st.button("Sign out", key="admin_out", use_container_width=True):
            auth.admin_logout()
            st.rerun()
        if database.backend_name() == "sqlite":
            st.markdown('<div class="ll-side-note">Using the local SQLite file. Data is not shared or kept on '
                        'Streamlit Cloud.</div>', unsafe_allow_html=True)

    ui.page_header("Admin dashboard", "Live overview of donors, requests and matches.", "chart")
    donors, reqs, matches_raw = db.donors_to_df(), db.recipients_to_df(), db.get_matches()
    matches = db.matches_to_df()
    if section == "Overview":
        _overview(donors, reqs, matches)
    elif section == "Donors":
        _donors(donors)
    elif section == "Requests":
        _requests(reqs)
    elif section == "Matches":
        _matches(matches_raw)
    else:
        _activity()
