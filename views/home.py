"""Page: Home — hero, live statistics, how it works, blood compatibility, safety & privacy."""

from __future__ import annotations

import streamlit as st

from config.constants import ALL_BLOOD_TYPES, BLOOD_COMPATIBILITY, BRAND_NAME, HOME_HEADLINE
from utils import db, nav, ui


def _donate_to(blood: str) -> list[str]:
    return [r for r in ALL_BLOOD_TYPES if blood in BLOOD_COMPATIBILITY[r]]


def render() -> None:
    # ── Hero ─────────────────────────────────────────────────────────────────
    with st.container(key="hero"):
        left, right = st.columns([1.15, 1], vertical_alignment="center", gap="large")
        with left:
            ui.render(f"""
            <div class="ll-hero">
            <span class="ll-badge">{ui.icon('heart', 16)} Welcome to the {BRAND_NAME} community</span>
            <h1>{ui.esc(HOME_HEADLINE)}</h1>
            <p class="lead">{BRAND_NAME} connects people who need blood or organs with willing donors nearby.
            Register once, search with clear compatibility information, and let a coordinator handle the
            introductions.</p></div>""")
            b1, b2 = st.columns(2)
            with b1:
                if st.button("Find a Donor", type="primary", use_container_width=True, key="hero_find"):
                    nav.go("matching")
            with b2:
                if st.button("Become a Donor", use_container_width=True, key="hero_donate"):
                    nav.go("donor")
        with right:
            ui.render(ui.hero_image())

    # ── Live statistics (real database counts) ───────────────────────────────
    stats = db.get_public_stats()
    st.write("")
    ui.stat_cards([
        ("Registered donors", stats["total_donors"], "users", "blue"),
        ("Blood & organ requests", stats["total_requests"], "drop", "sage"),
        ("Successful matches", stats["successful_matches"], "link", "blue"),
        ("Lives impacted", stats["fulfilled_requests"], "heart", "sage"),
    ])
    st.caption("Counts come directly from our records. “Lives impacted” is the number of requests marked fulfilled.")

    # ── How it works ─────────────────────────────────────────────────────────
    ui.section("How LifeLink works", "Four simple steps from sign-up to a saved life.")
    steps = [
        ("Register", "Donors share their blood group, city and availability. Families post a request with the hospital and urgency."),
        ("Find / Match", "Our matching engine scores donors on blood compatibility, location, urgency and availability."),
        ("Connect", "A coordinator reviews saved matches and contacts both sides — phone numbers are never shown publicly."),
        ("Save lives", "Once the donation is complete, the request is marked fulfilled so the community can see the impact."),
    ]
    ui.card_grid([
        f'<div class="ll-card ll-step"><div class="num">{i}</div><h3>{ui.esc(t)}</h3><p>{ui.esc(d)}</p></div>'
        for i, (t, d) in enumerate(steps, 1)
    ], cols=4)

    # ── Blood compatibility ──────────────────────────────────────────────────
    ui.section("Blood compatibility at a glance", "Pick a blood group to see who can give to it and receive from it.")
    c1, c2 = st.columns([1, 2], gap="large")
    with c1:
        blood = st.selectbox("Blood group", ALL_BLOOD_TYPES, index=ALL_BLOOD_TYPES.index("O+"), key="home_blood")
    with c2:
        recv = BLOOD_COMPATIBILITY[blood]
        give = _donate_to(blood)
        ui.render(f"""
        <div class="ll-grid c2">
        <div class="ll-card ivory"><h3 style="margin-top:0">{blood} can receive from</h3>
        <p>{' '.join(ui.pill(b, 'info') for b in recv)}</p></div>
        <div class="ll-card ivory"><h3 style="margin-top:0">{blood} can donate to</h3>
        <p>{' '.join(ui.pill(b, 'ok') for b in give)}</p></div></div>""")
    with st.expander("See the full compatibility table"):
        rows = "".join(
            f"<tr><td><b>{r}</b></td><td>{', '.join(lst)}</td></tr>"
            for r, lst in BLOOD_COMPATIBILITY.items()
        )
        ui.render(f'<table style="width:100%;border-collapse:collapse"><tr style="text-align:left;color:var(--muted)">'
                  f'<th>Recipient</th><th>Compatible donors</th></tr>{rows}</table>')
    st.caption("General guidance only. Final compatibility is always confirmed by laboratory testing and a clinician.")

    # ── Safety & privacy ─────────────────────────────────────────────────────
    ui.section("Safety and privacy come first", "Built for stressful moments, designed to protect everyone involved.")
    ui.card_grid([
        ui.card("Your contact details stay private",
                "Search results show only a donor ID, blood group, city and availability. Phone numbers and emails "
                "are visible to authorised coordinators only.", "eyeoff", "sage"),
        ui.card("Coordination, not clinical approval",
                "Match scores help prioritise outreach. Screening, cross-matching and the final decision always "
                "belong to qualified healthcare professionals.", "shield"),
        ui.card("Emergency? Call first",
                "If someone is in immediate danger, call 112 or contact the treating hospital right away — "
                "then use LifeLink to widen the search.", "alert", "sage"),
    ], cols=3)

    # ── Community call to action ─────────────────────────────────────────────
    st.write("")
    with st.container(key="banner"):
        t, b = st.columns([2, 1], vertical_alignment="center", gap="large")
        with t:
            st.markdown("## Care connects us all.")
            st.markdown("Join the community of donors who are ready when someone needs help. Registering takes "
                        "about two minutes.")
        with b:
            if st.button("Register as a donor", type="primary", use_container_width=True, key="banner_donate"):
                nav.go("donor")
            if st.button("Request blood", use_container_width=True, key="banner_request"):
                nav.go("request")
