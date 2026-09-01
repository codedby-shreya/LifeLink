"""
Page: Recipient / Urgent Request
"""

import streamlit as st
from config.constants import ALL_BLOOD_TYPES, ORGAN_TYPES, INDIAN_STATES, DONATION_TYPES, URGENCY_LEVELS
from utils.db import add_recipient, recipients_to_df, update_recipient_status
from utils.ai_helper import triage_urgency


def render():
    st.title("🆘 Post an Urgent Request")
    st.caption("Register a recipient's need for blood or organ donation.")

    api_key = st.session_state.get("gemini_api_key", "")

    tab_post, tab_view = st.tabs(["📝 Post Urgent Request", "📋 Active Requests"])

    # ─────────────────────────────────────────────────────────────────────────
    with tab_post:
        with st.form("recipient_form", clear_on_submit=True):
            st.subheader("Patient Information")
            col1, col2, col3 = st.columns(3)
            with col1:
                name = st.text_input("Patient Full Name *", placeholder="e.g. Priya Sharma")
            with col2:
                age = st.number_input("Age *", min_value=0, max_value=120, value=35)
            with col3:
                gender = st.selectbox("Gender *", ["Male", "Female", "Other"])

            col4, col5 = st.columns(2)
            with col4:
                phone = st.text_input("Contact Phone *", placeholder="+91 XXXXX XXXXX")
            with col5:
                email = st.text_input("Contact Email", placeholder="contact@hospital.com")

            st.divider()
            st.subheader("Medical Need")

            col6, col7 = st.columns(2)
            with col6:
                blood_type = st.selectbox("Patient Blood Type *", ALL_BLOOD_TYPES)
            with col7:
                need_type = st.selectbox("Type of Need *", DONATION_TYPES)

            organ_needed = ""
            if need_type == "Organ":
                organ_needed = st.selectbox("Organ Required *", ORGAN_TYPES)

            urgency = st.select_slider(
                "Urgency Level *",
                options=URGENCY_LEVELS,
                value=URGENCY_LEVELS[1],
            )

            medical_notes = st.text_area(
                "Medical Summary / Notes *",
                placeholder="Describe the patient's condition, diagnosis, and why donation is needed…",
                height=120,
            )

            st.divider()
            st.subheader("Location & Hospital")
            col8, col9 = st.columns(2)
            with col8:
                city = st.text_input("City *", placeholder="e.g. Delhi")
            with col9:
                state = st.selectbox("State *", INDIAN_STATES)
            hospital = st.text_input("Hospital Name *", placeholder="e.g. AIIMS Delhi")

            st.divider()
            consent = st.checkbox(
                "I confirm this request is genuine and I authorise sharing patient data "
                "for donor matching purposes."
            )

            submitted = st.form_submit_button("🚨 Post Urgent Request", use_container_width=True, type="primary")

        if submitted:
            errors = []
            if not name.strip():
                errors.append("Patient name is required.")
            if not phone.strip():
                errors.append("Contact phone is required.")
            if not city.strip():
                errors.append("City is required.")
            if not hospital.strip():
                errors.append("Hospital name is required.")
            if not medical_notes.strip():
                errors.append("Medical notes are required.")
            if not consent:
                errors.append("Consent must be provided.")

            if errors:
                for e in errors:
                    st.error(e)
            else:
                recipient = add_recipient(
                    name=name.strip(),
                    age=int(age),
                    gender=gender,
                    blood_type=blood_type,
                    need_type=need_type,
                    organ_needed=organ_needed,
                    city=city.strip(),
                    state=state,
                    hospital=hospital.strip(),
                    phone=phone.strip(),
                    email=email.strip(),
                    urgency=urgency,
                    medical_notes=medical_notes.strip(),
                )
                st.success(
                    f"✅ Request posted for **{recipient['name']}** (ID: **{recipient['id']}**). "
                    "Head to the **Matching Engine** to find compatible donors."
                )

                # AI urgency triage
                if api_key and medical_notes.strip():
                    with st.spinner("AI is analysing urgency level…"):
                        triage = triage_urgency(medical_notes.strip(), urgency)
                    st.info(f"**AI Urgency Assessment:**\n\n{triage}")
                else:
                    if not api_key:
                        st.warning("Add your Gemini API key in the sidebar to enable AI urgency triage.")

    # ─────────────────────────────────────────────────────────────────────────
    with tab_view:
        df = recipients_to_df()
        if df.empty:
            st.info("No requests posted yet.")
        else:
            # Summary
            total   = len(df)
            open_r  = (df["status"] == "Open").sum() if "status" in df.columns else 0
            critical = df["urgency"].str.contains("Critical", na=False).sum() if "urgency" in df.columns else 0

            col1, col2, col3 = st.columns(3)
            col1.metric("Total Requests", total)
            col2.metric("Open Requests", open_r)
            col3.metric("Critical Cases", critical)

            st.divider()

            # Filters
            col_f1, col_f2 = st.columns(2)
            with col_f1:
                filter_blood = st.multiselect("Filter by Blood Type", ALL_BLOOD_TYPES, key="r_blood_filter")
            with col_f2:
                filter_urgency = st.multiselect("Filter by Urgency", URGENCY_LEVELS, key="r_urg_filter")

            filtered = df.copy()
            if filter_blood:
                filtered = filtered[filtered["blood_type"].isin(filter_blood)]
            if filter_urgency:
                filtered = filtered[filtered["urgency"].isin(filter_urgency)]

            display_cols = ["id", "name", "age", "blood_type", "need_type", "organ_needed",
                            "urgency", "hospital", "city", "state", "status", "posted_at"]
            show_cols = [c for c in display_cols if c in filtered.columns]
            st.dataframe(filtered[show_cols], use_container_width=True, hide_index=True)

            # Status update
            st.divider()
            st.subheader("Update Request Status")
            rids = [r["id"] for r in st.session_state.get("recipients", [])]
            if rids:
                col_u1, col_u2, col_u3 = st.columns([2, 2, 1])
                with col_u1:
                    sel_id = st.selectbox("Select Request ID", rids, key="status_sel")
                with col_u2:
                    new_status = st.selectbox("New Status", ["Open", "In Progress", "Fulfilled", "Cancelled"], key="status_new")
                with col_u3:
                    st.write("")
                    st.write("")
                    if st.button("Update", use_container_width=True):
                        update_recipient_status(sel_id, new_status)
                        st.success(f"Status updated to **{new_status}**.")
                        st.rerun()
