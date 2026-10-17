"""
Page: AI Assistant (Gemini-powered chat — unchanged provider and behaviour).

The conversation is temporary UI state (st.session_state): it is not written to the
database, so nothing a user types is retained after their session ends.
"""

from __future__ import annotations

import datetime as dt

import streamlit as st

from utils import ai_helper, ui

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
_MAX_INPUT = 1500
_MAX_HISTORY = 20


def _history() -> list[dict]:
    return st.session_state.setdefault("chat_history", [])


def _queue(text: str) -> None:
    st.session_state["_chat_pending"] = text


def _retry() -> None:
    err = st.session_state.pop("chat_error", None)
    if err:
        st.session_state["_chat_pending"] = err[0]


def _clear() -> None:
    for k in ("chat_history", "chat_error", "_chat_pending"):
        st.session_state.pop(k, None)


def _stamp() -> str:
    return dt.datetime.now().strftime("%I:%M %p")


def render() -> None:
    ui.page_header("AI assistant", "Ask about blood groups, donation eligibility or how matching works.", "chat")

    if not ai_helper.ai_available():
        ui.empty_state("The assistant is not available right now",
                       "It hasn't been switched on for this deployment. Everything else in LifeLink still works.", "chat")
        return

    ui.notice("info", "The assistant gives general information only. It can't replace emergency services, a doctor, or "
                      "laboratory compatibility testing. Please don't share names or phone numbers here.")

    history = _history()
    if not history and "chat_error" not in st.session_state:
        st.markdown("**Try asking**")
        cols = st.columns(2)
        for i, text in enumerate(_SUGGESTIONS):
            cols[i % 2].button(text, key=f"sug_{i}", use_container_width=True, on_click=_queue, args=(text,))

    for msg in history:
        with st.chat_message(msg["role"]):
            st.markdown(msg["content"])
            st.caption(msg.get("ts", ""))

    typed = st.chat_input("Ask LifeLink AI about donation…", max_chars=_MAX_INPUT)
    message = (typed or st.session_state.pop("_chat_pending", None) or "").strip()

    if message:
        st.session_state.pop("chat_error", None)
        with st.chat_message("user"):
            st.markdown(message)
        with st.chat_message("assistant"):
            try:
                with st.spinner("LifeLink AI is thinking…"):
                    reply = ai_helper.chat_with_context(message[:_MAX_INPUT], history[-_MAX_HISTORY:])
            except ai_helper.AIUnavailable as exc:
                st.session_state["chat_error"] = (message, str(exc))
                st.rerun()
            else:
                st.markdown(reply)
        history.append({"role": "user", "content": message, "ts": _stamp()})
        history.append({"role": "assistant", "content": reply, "ts": _stamp()})
        st.rerun()

    err = st.session_state.get("chat_error")
    if err:
        ui.notice("warn", err[1], "That didn't go through.")
        st.button("Try again", type="primary", key="chat_retry", on_click=_retry)

    if history:
        st.divider()
        st.button("Clear conversation", key="chat_clear", on_click=_clear)
