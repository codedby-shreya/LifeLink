"""
Page: AI Assistant (Gemini-powered chat)
"""

import streamlit as st
from utils.db import append_chat, get_chat_history, clear_chat
from utils.ai_helper import chat_with_context


_SUGGESTIONS = [
    "What is the difference between O+ and O- blood types for donation?",
    "Who can donate a kidney and what are the eligibility criteria?",
    "How does blood type compatibility work for organ transplants?",
    "What should a first-time blood donor expect?",
    "How urgent is a 'Critical' urgency level and what should hospitals do?",
    "Can someone with diabetes donate blood or organs?",
    "What is HLA matching and why does it matter for organ transplants?",
    "Explain the matching score — what does a score of 85/100 mean?",
]


def render():
    st.title("🤖 AI Assistant — LifeLink AI")
    st.caption("Powered by Google Gemini · Ask anything about blood/organ donation, compatibility, or this platform.")

    api_key = st.session_state.get("gemini_api_key", "")

    if not api_key:
        st.warning(
            "⚠️ **Gemini API key not set.**\n\n"
            "Please enter your Google Gemini API key in the **sidebar** to use the AI assistant."
        )
        st.info(
            "Get your free API key at [Google AI Studio](https://aistudio.google.com/app/apikey). "
            "It's free for personal use."
        )
        return

    # ── Suggested prompts ─────────────────────────────────────────────────────
    history = get_chat_history()
    if not history:
        st.markdown("**💡 Suggested questions:**")
        cols = st.columns(2)
        for idx, suggestion in enumerate(_SUGGESTIONS):
            with cols[idx % 2]:
                if st.button(suggestion, key=f"sug_{idx}", use_container_width=True):
                    st.session_state["_pending_message"] = suggestion

    # ── Render chat history ───────────────────────────────────────────────────
    for msg in history:
        with st.chat_message(msg["role"]):
            st.markdown(msg["content"])
            st.caption(msg.get("ts", ""))

    # ── Handle pending (suggestion-click) messages ────────────────────────────
    if "_pending_message" in st.session_state:
        pending = st.session_state.pop("_pending_message")
        st.session_state["_run_message"] = pending
        st.rerun()

    if "_run_message" in st.session_state:
        user_input = st.session_state.pop("_run_message")
        _process_message(user_input, api_key)

    # ── Chat input ────────────────────────────────────────────────────────────
    user_input = st.chat_input("Ask LifeLink AI anything about donation…")
    if user_input:
        _process_message(user_input, api_key)

    # ── Clear chat ────────────────────────────────────────────────────────────
    if history:
        st.divider()
        if st.button("🗑️ Clear conversation", use_container_width=False):
            clear_chat()
            st.rerun()


def _process_message(user_input: str, api_key: str):
    """Append user message, call Gemini, append assistant reply."""
    append_chat("user", user_input)

    with st.chat_message("user"):
        st.markdown(user_input)

    with st.chat_message("assistant"):
        with st.spinner("LifeLink AI is thinking…"):
            # Build history excluding the message we just appended (last item)
            history = get_chat_history()
            prior_history = history[:-1]  # exclude the just-appended user message
            reply = chat_with_context(user_input, prior_history)
        st.markdown(reply)

    append_chat("assistant", reply)
    st.rerun()
