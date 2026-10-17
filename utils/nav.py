"""Navigation: one place that defines the pages and their URLs."""

from __future__ import annotations

import streamlit as st


def _home():
    from views.home import render
    render()


def _donor():
    from views.donor_registration import render
    render()


def _request():
    from views.recipient_request import render
    render()


def _matching():
    from views.matching_engine import render
    render()


def _assistant():
    from views.ai_assistant import render
    render()


def _admin():
    from views.admin_dashboard import render
    render()


def build_pages() -> dict[str, "st.Page"]:
    return {
        "home":      st.Page(_home,      title="Home",             icon=":material/home:", default=True),
        "donor":     st.Page(_donor,     title="Become a Donor",   icon=":material/volunteer_activism:", url_path="become-a-donor"),
        "request":   st.Page(_request,   title="Request Blood",    icon=":material/emergency:",     url_path="request-blood"),
        "matching":  st.Page(_matching,  title="Find a Donor",     icon=":material/search:",        url_path="find-a-donor"),
        "assistant": st.Page(_assistant, title="AI Assistant",     icon=":material/chat:",          url_path="ai-assistant"),
        "admin":     st.Page(_admin,     title="Admin Dashboard",  icon=":material/dashboard:",     url_path="admin"),
    }


def go(key: str) -> None:
    """Switch to a page by key."""
    st.switch_page(build_pages()[key])
