"""
Page: Matching Engine
"""

from __future__ import annotations
import streamlit as st
from config.constants import ALL_BLOOD_TYPES, URGENCY_LEVELS
from utils.db import (
    get_donors, get_recipients, save_match,
    get_recipient_by_id, get_donor_by_id,
)
from utils.matching import match_donors_to_recipient, find_recipients_for_donor
from utils.ai_helper import explain_match, suggest_next_steps


def _score_colour(score: float) -> str:
    if score >= 80:
        return "🟢"
    if score >= 60:
        return "🟡"
    return "🔴"


def render():
    st.title("🔗 Matching Engine")
    st.caption("Automatically match donors with recipients based on blood type, organs, location, and urgency.")

    api_key = st.session_state.get("gemini_api_key", "")

    mode = st.radio(
        "Matching Mode",
        ["Find donors for a recipient", "Find recipients for a donor"],
        horizontal=True,
    )

    donors     = get_donors(available_only=True)
    recipients = get_recipients(open_only=True)

    st.divider()

    # ── Mode 1: Donors → Recipient ────────────────────────────────────────────
    if mode == "Find donors for a recipient":
        if not recipients:
            st.warning("No open recipient requests found. Post an urgent request first.")
            return
        if not donors:
            st.warning("No available donors found. Register donors first.")
            return

        recip_options = {f"{r['id']} — {r['name']} ({r['blood_type']}, {r.get('organ_needed') or 'Blood'}, {r['urgency']})": r["id"]
                         for r in recipients}
        selected_label = st.selectbox("Select Recipient Request", list(recip_options.keys()))
        recipient_id   = recip_options[selected_label]
        recipient      = get_recipient_by_id(recipient_id)

        if not recipient:
            st.error("Recipient not found.")
            return

        # Recipient summary card
        with st.expander("📋 Recipient Details", expanded=True):
            col1, col2, col3, col4 = st.columns(4)
            col1.metric("Blood Type", recipient["blood_type"])
            col2.metric("Needs", recipient.get("organ_needed") or "Blood")
            col3.metric("Urgency", recipient["urgency"])
            col4.metric("Location", f"{recipient['city']}, {recipient['state']}")
            if recipient.get("medical_notes"):
                st.caption(f"📝 {recipient['medical_notes'][:200]}…" if len(recipient.get('medical_notes','')) > 200 else f"📝 {recipient['medical_notes']}")

        top_n = st.slider("Number of matches to show", 3, 20, 5)

        if st.button("🔍 Run Matching Algorithm", use_container_width=True, type="primary"):
            with st.spinner("Finding best matches…"):
                matches = match_donors_to_recipient(recipient, donors, top_n=top_n)

            if not matches:
                st.error("No compatible donors found for this recipient.")
                if api_key:
                    next_steps = suggest_next_steps(recipient, None)
                    st.info(f"**AI Suggested Next Steps:**\n\n{next_steps}")
                return

            st.success(f"Found **{len(matches)}** compatible donor(s).")

            # AI next steps
            if api_key:
                with st.spinner("AI is generating next steps…"):
                    next_steps = suggest_next_steps(recipient, matches[0])
                st.info(f"**AI Suggested Next Steps:**\n\n{next_steps}")

            st.divider()
            for i, m in enumerate(matches):
                donor = m["donor"]
                score = m["total_score"]
                icon  = _score_colour(score)
                with st.container(border=True):
                    c1, c2, c3, c4, c5 = st.columns([3, 1, 1, 1, 2])
                    c1.markdown(f"**#{i+1} {icon} {donor['name']}** (ID: {donor['id']})")
                    c2.metric("Score", f"{score}/100")
                    c3.metric("Blood", donor["blood_type"])
                    c4.metric("Location", f"{donor['city']}")
                    c5.caption(f"{donor['state']} | {donor.get('phone', '—')}")

                    with st.expander("View breakdown & AI explanation"):
                        b1, b2, b3, b4 = st.columns(4)
                        b1.metric("Blood Score", f"{m['blood_score']}/100")
                        b2.metric("Location Score", f"{m['location_score']}/100")
                        b3.metric("Urgency Score", f"{m['urgency_score']}/100")
                        b4.metric("Availability", f"{m['availability_score']}/100")

                        st.markdown("**Matching factors:**")
                        for reason in m["reasons"]:
                            st.markdown(f"- {reason}")

                        if donor.get("medical_notes"):
                            st.caption(f"Donor notes: {donor['medical_notes']}")

                        if api_key:
                            if st.button(f"💡 AI Explanation", key=f"explain_{i}"):
                                with st.spinner("Generating AI explanation…"):
                                    explanation = explain_match(m)
                                st.info(explanation)

                        if st.button(f"💾 Save Match", key=f"save_{i}"):
                            save_match(donor["id"], recipient["id"], score, {
                                "reasons": m["reasons"],
                                "blood_score": m["blood_score"],
                                "location_score": m["location_score"],
                            })
                            st.success(f"Match saved: Donor **{donor['name']}** ↔ Recipient **{recipient['name']}**")

    # ── Mode 2: Recipients → Donor ────────────────────────────────────────────
    else:
        if not donors:
            st.warning("No available donors found. Register donors first.")
            return
        if not recipients:
            st.warning("No open recipient requests found. Post an urgent request first.")
            return

        donor_options = {f"{d['id']} — {d['name']} ({d['blood_type']}, {d['donation_type']}, {d['city']})": d["id"]
                         for d in donors}
        selected_label = st.selectbox("Select Donor", list(donor_options.keys()))
        donor_id       = donor_options[selected_label]
        donor          = get_donor_by_id(donor_id)

        if not donor:
            st.error("Donor not found.")
            return

        with st.expander("📋 Donor Details", expanded=True):
            col1, col2, col3, col4 = st.columns(4)
            col1.metric("Blood Type", donor["blood_type"])
            col2.metric("Donation Type", donor["donation_type"])
            col3.metric("Organs", ", ".join(donor.get("organs") or []) or "Blood")
            col4.metric("Location", f"{donor['city']}, {donor['state']}")

        top_n = st.slider("Number of matches to show", 3, 20, 5)

        if st.button("🔍 Find Matching Recipients", use_container_width=True, type="primary"):
            with st.spinner("Scanning recipient list…"):
                matches = find_recipients_for_donor(donor, recipients, top_n=top_n)

            if not matches:
                st.error("No matching recipients found for this donor currently.")
                return

            st.success(f"Found **{len(matches)}** matching recipient(s).")
            st.divider()

            for i, m in enumerate(matches):
                recip = m["recipient"]
                score = m["total_score"]
                icon  = _score_colour(score)
                with st.container(border=True):
                    c1, c2, c3, c4, c5 = st.columns([3, 1, 1, 1, 2])
                    c1.markdown(f"**#{i+1} {icon} {recip['name']}** (ID: {recip['id']})")
                    c2.metric("Score", f"{score}/100")
                    c3.metric("Blood", recip["blood_type"])
                    c4.metric("Urgency", recip["urgency"].split(" ")[0])
                    c5.caption(f"{recip['hospital']} | {recip['city']}, {recip['state']}")

                    with st.expander("View breakdown"):
                        b1, b2, b3 = st.columns(3)
                        b1.metric("Blood Score", f"{m['blood_score']}/100")
                        b2.metric("Location Score", f"{m['location_score']}/100")
                        b3.metric("Urgency Score", f"{m['urgency_score']}/100")

                        st.markdown("**Matching factors:**")
                        for reason in m["reasons"]:
                            st.markdown(f"- {reason}")

                        if st.button(f"💾 Save Match", key=f"save_r_{i}"):
                            save_match(donor["id"], recip["id"], score, {
                                "reasons": m["reasons"],
                                "blood_score": m["blood_score"],
                                "location_score": m["location_score"],
                            })
                            st.success(f"Match saved!")
