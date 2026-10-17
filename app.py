"""
LifeLink — Care connects us all.
Main Streamlit entry point: page config, theme, database check, navigation.
"""

import streamlit as st

from config.constants import APP_ICON, BRAND_NAME, BRAND_TAGLINE

# Page config must be the first Streamlit call.
st.set_page_config(
    page_title=f"{BRAND_NAME} — {BRAND_TAGLINE}",
    page_icon=APP_ICON,
    layout="wide",
    initial_sidebar_state="auto",
)

try:  # local development: load .env if python-dotenv is available
    from dotenv import load_dotenv
    load_dotenv()
except ImportError:  # pragma: no cover
    pass

from utils import database, db, nav, ui  # noqa: E402

ui.inject_css()
ui.setup_chrome()


def _problem(title: str, text: str) -> None:
    ui.page_header(title, "", "alert")
    ui.notice("warn", text)
    if st.button("Try again", type="primary", key="db_retry"):
        database.reset_connections()
        st.rerun()
    ui.footer()


try:
    db.init_db()
except database.SchemaMissing as exc:
    _problem("Database setup needed", str(exc))
    st.stop()
except database.DatabaseUnavailable:
    _problem("We can't reach the database right now",
             "Your data is safe. This is usually brief — please try again in a minute. If it keeps happening, "
             "the site administrator should check the database connection.")
    st.stop()

pages = nav.build_pages()
page = st.navigation(list(pages.values()))

with st.sidebar:
    st.markdown(f'<div class="ll-side-note">{BRAND_TAGLINE}<br>In an emergency call <b>112</b> or the treating hospital first.</div>',
                unsafe_allow_html=True)

try:
    page.run()
except database.SchemaMissing as exc:
    _problem("Database setup needed", str(exc))
except database.DatabaseUnavailable:
    _problem("We can't reach the database right now",
             "Your data is safe. This is usually brief — please try again in a minute.")
else:
    ui.footer()
