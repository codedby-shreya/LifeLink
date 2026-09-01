"""
LifeLink — Blood & Organ Donor Matching Platform
Main Streamlit entry point.
"""

import os
import pandas as pd
import streamlit as st

from config.constants import APP_TITLE, APP_ICON, APP_DESCRIPTION, BLOOD_COMPATIBILITY
from utils.db import init_db

# ── Page config (must be the very first Streamlit call) ───────────────────────
st.set_page_config(
    page_title=APP_TITLE,
    page_icon=APP_ICON,
    layout="wide",
    initial_sidebar_state="expanded",
)

# ── Initialise session-state DB ───────────────────────────────────────────────
init_db()

# ── Auto-load API key from Streamlit Cloud secrets (if available) ─────────────
if "gemini_api_key" not in st.session_state:
    try:
        _secret_key = st.secrets.get("GEMINI_API_KEY", "")
        if _secret_key:
            st.session_state["gemini_api_key"] = _secret_key
            from utils.ai_helper import init_gemini
            init_gemini(_secret_key)
    except Exception:
        pass  # Running locally without secrets — key entered via sidebar


# ── Home page renderer ────────────────────────────────────────────────────────

def _render_home():
    st.title(f"{APP_ICON} Welcome to LifeLink")
    st.subheader(APP_DESCRIPTION)

    st.divider()

    donors_n     = len(st.session_state.get("donors", []))
    recipients_n = len(st.session_state.get("recipients", []))
    matches_n    = len(st.session_state.get("matches", []))

    c1, c2, c3, c4 = st.columns(4)
    c1.metric("🩸 Registered Donors",  donors_n)
    c2.metric("🆘 Urgent Requests",    recipients_n)
    c3.metric("🔗 Matches Made",       matches_n)
    c4.metric("💊 Lives Impacted",     matches_n)

    st.divider()

    col1, col2 = st.columns(2)

    with col1:
        st.subheader("🩺 How to Register as a Donor")
        st.markdown("""
1. Go to **Donor Registration** in the sidebar.
2. Fill in your personal and medical details.
3. Select your blood type and organs available for donation.
4. Submit — you are now part of the matching pool!
""")
        st.subheader("🆘 How to Post an Urgent Request")
        st.markdown("""
1. Go to **Urgent Request** in the sidebar.
2. Fill in the patient's blood type, organ needed, and urgency level.
3. Submit — the request goes live immediately.
4. Head to the **Matching Engine** to find compatible donors.
""")

    with col2:
        st.subheader("🔗 How the Matching Works")
        st.markdown("""
Our AI-powered matching algorithm scores each donor–recipient pair on:

| Factor | Weight |
|---|---|
| 🩸 Blood type compatibility | 40 % |
| 📍 Geographic proximity | 30 % |
| ⚡ Urgency level | 20 % |
| ✅ Donor availability | 10 % |

Scores are out of **100**. Higher is better.  
≥ 80 → Strong match &nbsp;|&nbsp; 60–79 → Acceptable &nbsp;|&nbsp; < 60 → Needs review
""")
        st.subheader("🤖 AI Assistant")
        st.markdown("""
Ask **LifeLink AI** (powered by Google Gemini) anything:
- Blood type compatibility questions  
- Organ donation eligibility criteria  
- Understanding match scores  
- Actionable next steps for hospital coordinators  
""")

    st.divider()

    st.subheader("🩸 Blood Type Compatibility Quick Reference")
    compat_data = [
        {
            "Recipient Blood Type": rbt,
            "Compatible Donor Blood Types": ", ".join(donors),
            "# Compatible Types": len(donors),
        }
        for rbt, donors in BLOOD_COMPATIBILITY.items()
    ]
    st.dataframe(pd.DataFrame(compat_data), use_container_width=True, hide_index=True)

    st.divider()
    st.caption(
        "⚠️ **Disclaimer:** LifeLink is a matching platform for informational purposes only. "
        "All actual donation decisions must be made under the supervision of licensed medical professionals. "
        "Always verify compatibility through certified medical testing before proceeding."
    )


# ── Sidebar ───────────────────────────────────────────────────────────────────

with st.sidebar:
    st.title(f"{APP_ICON} LifeLink")
    st.caption("Blood & Organ Donor Matching Platform")
    st.divider()

    page = st.radio(
        "Navigation",
        options=[
            "🏠 Home",
            "🩺 Donor Registration",
            "🆘 Urgent Request",
            "🔗 Matching Engine",
            "🤖 AI Assistant",
            "📊 Admin Dashboard",
        ],
        label_visibility="collapsed",
    )

    st.divider()

    donors_n     = len(st.session_state.get("donors", []))
    recipients_n = len(st.session_state.get("recipients", []))
    matches_n    = len(st.session_state.get("matches", []))
    c1, c2, c3 = st.columns(3)
    c1.metric("Donors",   donors_n)
    c2.metric("Requests", recipients_n)
    c3.metric("Matches",  matches_n)

    st.divider()
    st.caption("LifeLink v1.0 · Powered by Gemini AI")


# ── Page routing ──────────────────────────────────────────────────────────────

if page == "🏠 Home":
    _render_home()

elif page == "🩺 Donor Registration":
    from views.donor_registration import render
    render()

elif page == "🆘 Urgent Request":
    from views.recipient_request import render
    render()

elif page == "🔗 Matching Engine":
    from views.matching_engine import render
    render()

elif page == "🤖 AI Assistant":
    from views.ai_assistant import render
    render()

elif page == "📊 Admin Dashboard":
    from views.admin_dashboard import render
    render()
