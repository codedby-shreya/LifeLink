"""
Gemini AI helper — uses the google-genai SDK (google.genai). Provider, model and
features are unchanged from the original project.

Changes in this version
  * API key is read from GEMINI_API_KEY (environment / .env / Streamlit secrets)
    and is never displayed, logged or put in an error message.
  * Prompts no longer include names, phone numbers or hospital names — only the
    clinical/matching facts the model needs (IDs stand in for people).
  * Failures raise AIUnavailable (with a friendly message) so pages can show a
    clear error and a Retry button instead of printing raw exceptions.
"""

from __future__ import annotations

import logging
import time

import streamlit as st
from google import genai
from google.genai import types

from config.constants import EMERGENCY_NUMBER_IN, GEMINI_MODEL
from utils.database import get_setting

log = logging.getLogger("lifelink.ai")

_MAX_RETRIES = 4
_RETRY_DELAYS = [2, 4, 8, 16]   # seconds between attempts on 503 / 429


class AIUnavailable(RuntimeError):
    """The AI service is not configured or could not answer. str(exc) is safe to show."""


# ── Initialisation ────────────────────────────────────────────────────────────

def get_api_key() -> str:
    return get_setting("GEMINI_API_KEY")


def ai_available() -> bool:
    return bool(get_api_key())


def init_gemini(api_key: str):
    """Configure the Gemini client for this session (kept server-side)."""
    st.session_state["_genai_client"] = genai.Client(api_key=api_key)


def _client() -> genai.Client:
    client = st.session_state.get("_genai_client")
    if client is None:
        key = get_api_key()
        if not key:
            raise AIUnavailable("The AI assistant is not configured on this deployment.")
        init_gemini(key)
        client = st.session_state["_genai_client"]
    return client


_SYSTEM_PROMPT = (
    "You are LifeLink AI — a compassionate and knowledgeable assistant specialising in "
    "blood and organ donation. Your role is to:\n"
    "1. Answer questions about blood type compatibility, organ donation eligibility, and the "
    "donation process clearly and accurately.\n"
    "2. Help users understand match results and what the scores mean.\n"
    "3. Provide empathetic guidance to both donors and recipients.\n"
    "4. Explain medical terms in simple language.\n"
    "5. Remind users that this platform is for informational/matching purposes only and that "
    "actual donation decisions must involve certified medical professionals.\n\n"
    "Always be kind, factual, and non-alarmist. Never give specific clinical advice or diagnoses. "
    f"If someone describes an emergency, tell them to call {EMERGENCY_NUMBER_IN} or contact the treating "
    "hospital immediately. Do not ask users for names, phone numbers or other personal details. "
    "Keep responses concise (under 300 words unless a detailed explanation is explicitly requested)."
)


def _is_transient(msg: str) -> bool:
    return "503" in msg or "UNAVAILABLE" in msg or "429" in msg or "quota" in msg.lower()


def _call(contents) -> str:
    """Shared call with retry. Raises AIUnavailable with a safe message."""
    last_err: Exception | None = None
    for attempt in range(_MAX_RETRIES):
        try:
            response = _client().models.generate_content(
                model=GEMINI_MODEL,
                contents=contents,
                config=types.GenerateContentConfig(system_instruction=_SYSTEM_PROMPT),
            )
            text = (response.text or "").strip()
            if not text:
                raise AIUnavailable("The AI returned an empty answer. Please try again.")
            return text
        except AIUnavailable:
            raise
        except Exception as exc:  # noqa: BLE001 — SDK raises many types
            last_err = exc
            if _is_transient(str(exc)) and attempt < _MAX_RETRIES - 1:
                time.sleep(_RETRY_DELAYS[attempt])
                continue
            break
    log.warning("Gemini request failed: %s", type(last_err).__name__)   # type only — no message, no key
    raise AIUnavailable(
        "The AI assistant is busy or unavailable right now. Please try again in a moment."
    ) from last_err


# ── Context-aware chat ────────────────────────────────────────────────────────

def chat_with_context(user_message: str, history: list[dict]) -> str:
    """history = list of {role: "user"|"assistant", content: str}. Raises AIUnavailable."""
    contents = []
    for msg in history:
        role = "user" if msg["role"] == "user" else "model"
        contents.append(types.Content(role=role, parts=[types.Part(text=msg["content"])]))
    contents.append(types.Content(role="user", parts=[types.Part(text=user_message)]))
    return _call(contents)


# ── One-shot utilities ────────────────────────────────────────────────────────

def _generate(prompt: str) -> str:
    return _call(prompt)


def explain_match(match_result: dict) -> str:
    """Human-readable explanation for a match result (no personal identifiers sent)."""
    donor, recip = match_result["donor"], match_result["recipient"]
    reasons = "\n".join(f"  • {r}" for r in match_result["reasons"])
    prompt = (
        "A donor-recipient match has been found on the LifeLink platform. Please write a short, "
        "warm, and informative explanation (2–3 sentences) for the coordinator reviewing "
        "this match. Include what makes this a good (or acceptable) match. Remind them that the "
        "score is software-generated and clinical compatibility must be confirmed by professionals.\n\n"
        f"Donor {donor['id']}: blood type {donor['blood_type']}, located in {donor['city']}, {donor['state']}\n"
        f"Request {recip['id']}: blood type {recip['blood_type']}, "
        f"needs {recip.get('organ_needed') or 'blood'}, urgency: {recip['urgency']}\n"
        f"Match score: {match_result['total_score']}/100\n\n"
        f"Matching factors:\n{reasons}"
    )
    return _generate(prompt)


def suggest_next_steps(recipient: dict, top_match: dict | None) -> str:
    """Actionable next steps for a request given its best match (no personal identifiers sent)."""
    if top_match:
        donor = top_match["donor"]
        context = (f"The best match found is donor {donor['id']} (Blood: {donor['blood_type']}, "
                   f"City: {donor['city']}, {donor['state']}) with a compatibility score of "
                   f"{top_match['total_score']}/100.")
    else:
        context = "No compatible donor has been found yet."
    prompt = (
        f"A patient (blood type {recipient['blood_type']}) needs "
        f"{recipient.get('organ_needed') or 'a blood transfusion'} (urgency: {recipient['urgency']}) "
        f"in {recipient['city']}, {recipient['state']}.\n\n{context}\n\n"
        "Please provide 3 concise, practical next steps the family or coordinator should take right now. "
        "Be clear and actionable. Include contacting the treating hospital's blood bank."
    )
    return _generate(prompt)


def analyse_donor_profile(donor: dict) -> str:
    """Brief AI profile note for a donor (non-identifying fields only)."""
    organs = ", ".join(donor.get("organs") or []) or "N/A"
    prompt = (
        "Analyse this organ/blood donor profile briefly (2-3 sentences) for a matching coordinator. "
        "Highlight any notable compatibility advantages and flag any considerations.\n\n"
        f"Age: {donor['age']}, Gender: {donor['gender']}\n"
        f"Blood type: {donor['blood_type']}, Donation type: {donor['donation_type']}\n"
        f"Organs registered: {organs}\n"
        f"Health notes: {donor.get('medical_notes') or 'None provided'}"
    )
    return _generate(prompt)


def triage_urgency(medical_notes: str, stated_urgency: str) -> str:
    """AI-assisted urgency triage based on the medical summary."""
    prompt = (
        f'A request has been registered with urgency level "{stated_urgency}". '
        f'The medical summary says: "{medical_notes}"\n\n'
        "Based solely on the notes provided, does the stated urgency level seem appropriate? "
        "Reply in 1-2 sentences, noting if the urgency should potentially be escalated or "
        "if it seems consistent. Be conservative — err on the side of higher urgency."
    )
    return _generate(prompt)
