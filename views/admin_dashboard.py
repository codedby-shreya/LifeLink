"""
Page: Admin Dashboard — analytics and match management
"""

from __future__ import annotations
import streamlit as st
import pandas as pd
import plotly.graph_objects as go
import plotly.express as px

from config.constants import ALL_BLOOD_TYPES, URGENCY_LEVELS
from utils.db import (
    donors_to_df, recipients_to_df, matches_to_df,
    get_matches, update_match_status, update_donor_availability,
    get_donors, get_recipients,
)


def _pie(values, labels, title):
    fig = go.Figure(go.Pie(values=values, labels=labels, hole=0.4, textinfo="label+percent"))
    fig.update_layout(title=title, margin=dict(t=40, b=10, l=10, r=10), height=320)
    return fig


def _bar(x, y, title, xlabel, ylabel, color="#3b82d4"):
    fig = go.Figure(go.Bar(x=x, y=y, marker_color=color))
    fig.update_layout(
        title=title,
        xaxis_title=xlabel,
        yaxis_title=ylabel,
        margin=dict(t=40, b=40, l=40, r=10),
        height=320,
    )
    return fig


def render():
    st.title("📊 Admin Dashboard")
    st.caption("Platform-wide analytics, donor/recipient management, and match tracking.")

    # ── KPI row ───────────────────────────────────────────────────────────────
    donors_df     = donors_to_df()
    recipients_df = recipients_to_df()
    matches_df    = matches_to_df()

    total_donors     = len(donors_df)
    total_recipients = len(recipients_df)
    total_matches    = len(matches_df)
    critical_cases   = (recipients_df["urgency"].str.contains("Critical", na=False).sum()
                        if not recipients_df.empty else 0)

    k1, k2, k3, k4 = st.columns(4)
    k1.metric("Total Donors", total_donors)
    k2.metric("Total Requests", total_recipients)
    k3.metric("Matches Made", total_matches)
    k4.metric("Critical Cases", critical_cases, delta=f"{critical_cases} open" if critical_cases else None,
              delta_color="inverse")

    st.divider()

    # ── Charts ────────────────────────────────────────────────────────────────
    tab_charts, tab_donors, tab_recipients, tab_matches = st.tabs([
        "📈 Analytics", "👤 Manage Donors", "🆘 Manage Requests", "🔗 Manage Matches"
    ])

    with tab_charts:
        if donors_df.empty and recipients_df.empty:
            st.info("Register donors and recipients to see analytics here.")
        else:
            col1, col2 = st.columns(2)

            # Blood type distribution — donors
            if not donors_df.empty:
                blood_counts_d = donors_df["blood_type"].value_counts().reset_index()
                blood_counts_d.columns = ["blood_type", "count"]
                with col1:
                    fig = _pie(blood_counts_d["count"].tolist(),
                               blood_counts_d["blood_type"].tolist(),
                               "Donor Blood Type Distribution")
                    st.plotly_chart(fig, use_container_width=True)

            # Blood type distribution — recipients
            if not recipients_df.empty:
                blood_counts_r = recipients_df["blood_type"].value_counts().reset_index()
                blood_counts_r.columns = ["blood_type", "count"]
                with col2:
                    fig = _pie(blood_counts_r["count"].tolist(),
                               blood_counts_r["blood_type"].tolist(),
                               "Recipient Blood Type Distribution")
                    st.plotly_chart(fig, use_container_width=True)

            # Urgency breakdown
            if not recipients_df.empty:
                urg_counts = recipients_df["urgency"].value_counts()
                colors = {"Critical (< 24 hrs)": "#dc2626", "Urgent (1–3 days)": "#f97316",
                          "Moderate (within a week)": "#eab308", "Stable": "#22c55e"}
                bar_colors = [colors.get(u, "#3b82d4") for u in urg_counts.index.tolist()]
                fig2 = go.Figure(go.Bar(
                    x=urg_counts.index.tolist(),
                    y=urg_counts.values.tolist(),
                    marker_color=bar_colors,
                ))
                fig2.update_layout(
                    title="Recipient Requests by Urgency Level",
                    xaxis_title="Urgency", yaxis_title="Count",
                    margin=dict(t=40, b=80, l=40, r=10), height=340
                )
                st.plotly_chart(fig2, use_container_width=True)

            # Donation type split — donors
            if not donors_df.empty:
                col3, col4 = st.columns(2)
                with col3:
                    dt_counts = donors_df["donation_type"].value_counts()
                    fig3 = _pie(dt_counts.values.tolist(), dt_counts.index.tolist(), "Donor Type Split")
                    st.plotly_chart(fig3, use_container_width=True)

                # State distribution — donors (top 10)
                with col4:
                    state_counts = donors_df["state"].value_counts().head(10)
                    fig4 = _bar(state_counts.index.tolist(), state_counts.values.tolist(),
                                "Top 10 States — Donors", "State", "Donors")
                    st.plotly_chart(fig4, use_container_width=True)

            # Match score distribution
            if not matches_df.empty and "Score" in matches_df.columns:
                fig5 = px.histogram(matches_df, x="Score", nbins=10,
                                    title="Match Score Distribution", color_discrete_sequence=["#3b82d4"])
                fig5.update_layout(margin=dict(t=40, b=40, l=40, r=10), height=320)
                st.plotly_chart(fig5, use_container_width=True)

    # ── Manage Donors ─────────────────────────────────────────────────────────
    with tab_donors:
        if donors_df.empty:
            st.info("No donors registered yet.")
        else:
            st.dataframe(donors_df, use_container_width=True, hide_index=True)

            st.divider()
            st.subheader("Toggle Donor Availability")
            donors_list = get_donors()
            if donors_list:
                d_options = {f"{d['id']} — {d['name']} (currently {'Available' if d['available'] else 'Unavailable'})": d["id"]
                             for d in donors_list}
                sel = st.selectbox("Select Donor", list(d_options.keys()), key="admin_donor_sel")
                new_avail = st.toggle("Mark as Available", value=True, key="admin_avail_toggle")
                if st.button("Update Availability", key="admin_avail_btn"):
                    update_donor_availability(d_options[sel], new_avail)
                    st.success("Availability updated.")
                    st.rerun()

    # ── Manage Recipients ─────────────────────────────────────────────────────
    with tab_recipients:
        if recipients_df.empty:
            st.info("No recipient requests posted yet.")
        else:
            # Highlight critical
            def highlight_critical(row):
                if "Critical" in str(row.get("urgency", "")):
                    return ["background-color: #fee2e2"] * len(row)
                return [""] * len(row)
            st.dataframe(recipients_df.style.apply(highlight_critical, axis=1),
                         use_container_width=True, hide_index=True)

    # ── Manage Matches ────────────────────────────────────────────────────────
    with tab_matches:
        if matches_df.empty:
            st.info("No matches saved yet. Use the Matching Engine to find and save matches.")
        else:
            st.dataframe(matches_df, use_container_width=True, hide_index=True)

            st.divider()
            st.subheader("Update Match Status")
            match_ids = [m["id"] for m in get_matches()]
            if match_ids:
                col_m1, col_m2, col_m3 = st.columns([2, 2, 1])
                with col_m1:
                    sel_mid = st.selectbox("Match ID", match_ids, key="match_status_sel")
                with col_m2:
                    new_mstatus = st.selectbox(
                        "New Status",
                        ["Pending Contact", "Contacted", "In Progress", "Completed", "Failed"],
                        key="match_new_status",
                    )
                with col_m3:
                    st.write("")
                    st.write("")
                    if st.button("Update", key="match_status_btn", use_container_width=True):
                        update_match_status(sel_mid, new_mstatus)
                        st.success(f"Match {sel_mid} updated to **{new_mstatus}**.")
                        st.rerun()
