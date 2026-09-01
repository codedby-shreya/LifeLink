"""
Page: Donor Registration
"""

import streamlit as st
from config.constants import ALL_BLOOD_TYPES, ORGAN_TYPES, INDIAN_STATES, DONATION_TYPES
from utils.db import add_donor, donors_to_df
from utils.ai_helper import analyse_donor_profile


def render():
    st.title("🩺 Donor Registration")
    st.caption("Register as a blood or organ donor to help save lives.")

    # ── Check API key ─────────────────────────────────────────────────────────
    api_key = st.session_state.get("gemini_api_key", "")

    tab_register, tab_view = st.tabs(["📝 Register as Donor", "📋 Registered Donors"])

    # ─────────────────────────────────────────────────────────────────────────
    with tab_register:
        with st.form("donor_form", clear_on_submit=True):
            st.subheader("Personal Information")
            col1, col2, col3 = st.columns(3)
            with col1:
                name = st.text_input("Full Name *", placeholder="e.g. Ravi Kumar")
            with col2:
                age = st.number_input("Age *", min_value=18, max_value=65, value=25)
            with col3:
                gender = st.selectbox("Gender *", ["Male", "Female", "Other"])

            col4, col5 = st.columns(2)
            with col4:
                phone = st.text_input("Phone Number *", placeholder="+91 XXXXX XXXXX")
            with col5:
                email = st.text_input("Email Address", placeholder="donor@example.com")

            st.divider()
            st.subheader("Medical Information")

            col6, col7 = st.columns(2)
            with col6:
                blood_type = st.selectbox("Blood Type *", ALL_BLOOD_TYPES)
            with col7:
                donation_type = st.selectbox("Donation Type *", DONATION_TYPES)

            organs = []
            if donation_type == "Organ":
                organs = st.multiselect(
                    "Organs Available for Donation *",
                    ORGAN_TYPES,
                    help="Select all organs you are willing to donate.",
                )

            medical_notes = st.text_area(
                "Medical Notes (optional)",
                placeholder="Any relevant health information, past surgeries, current medications…",
                height=80,
            )

            st.divider()
            st.subheader("Location")
            col8, col9 = st.columns(2)
            with col8:
                city = st.text_input("City *", placeholder="e.g. Mumbai")
            with col9:
                state = st.selectbox("State *", INDIAN_STATES)

            st.divider()
            consent = st.checkbox(
                "I consent to share my information for donor-recipient matching purposes. "
                "I understand this platform is for matching only and actual donation requires medical evaluation."
            )

            submitted = st.form_submit_button("✅ Register as Donor", use_container_width=True, type="primary")

        if submitted:
            # Validation
            errors = []
            if not name.strip():
                errors.append("Full name is required.")
            if not phone.strip():
                errors.append("Phone number is required.")
            if not city.strip():
                errors.append("City is required.")
            if donation_type == "Organ" and not organs:
                errors.append("Please select at least one organ.")
            if not consent:
                errors.append("You must provide consent to register.")

            if errors:
                for e in errors:
                    st.error(e)
            else:
                donor = add_donor(
                    name=name.strip(),
                    age=int(age),
                    gender=gender,
                    blood_type=blood_type,
                    donation_type=donation_type,
                    organs=organs,
                    city=city.strip(),
                    state=state,
                    phone=phone.strip(),
                    email=email.strip(),
                    medical_notes=medical_notes.strip(),
                )
                st.success(f"🎉 Thank you, **{donor['name']}**! Your donor ID is **{donor['id']}**. You've been registered successfully.")

                # AI profile analysis
                if api_key:
                    with st.spinner("Generating AI profile analysis…"):
                        analysis = analyse_donor_profile(donor)
                    st.info(f"**AI Profile Analysis:**\n\n{analysis}")
                else:
                    st.warning("Add your Gemini API key in the sidebar to enable AI profile analysis.")

    # ─────────────────────────────────────────────────────────────────────────
    with tab_view:
        df = donors_to_df()
        if df.empty:
            st.info("No donors registered yet. Be the first to register!")
        else:
            # Summary metrics
            col1, col2, col3 = st.columns(3)
            col1.metric("Total Donors", len(df))
            col2.metric("Available Donors", df["available"].sum() if "available" in df.columns else 0)
            col3.metric("Organ Donors", (df["donation_type"] == "Organ").sum() if "donation_type" in df.columns else 0)

            st.divider()

            # Filters
            col_f1, col_f2, col_f3 = st.columns(3)
            with col_f1:
                filter_blood = st.multiselect("Filter by Blood Type", ALL_BLOOD_TYPES, key="d_blood_filter")
            with col_f2:
                filter_type = st.multiselect("Filter by Donation Type", DONATION_TYPES, key="d_type_filter")
            with col_f3:
                filter_state = st.multiselect("Filter by State", sorted(df["state"].unique().tolist()), key="d_state_filter")

            filtered = df.copy()
            if filter_blood:
                filtered = filtered[filtered["blood_type"].isin(filter_blood)]
            if filter_type:
                filtered = filtered[filtered["donation_type"].isin(filter_type)]
            if filter_state:
                filtered = filtered[filtered["state"].isin(filter_state)]

            display_cols = ["id", "name", "age", "gender", "blood_type", "donation_type",
                            "organs", "city", "state", "available", "registered_at"]
            show_cols = [c for c in display_cols if c in filtered.columns]
            st.dataframe(filtered[show_cols], use_container_width=True, hide_index=True)
