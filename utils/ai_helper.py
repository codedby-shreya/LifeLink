"""
Gemini AI helper — uses the new google-genai SDK (google.genai).
"""

from __future__ import annotations
import time
import streamlit as st
from google import genai
from google.genai import types
from config.constants import GEMINI_MODEL

# Retry settings for 503 / transient errors
_MAX_RETRIES = 4
_RETRY_DELAYS = [2, 4, 8, 16]   # seconds between each attempt


# ── Initialisation ────────────────────────────────────────────────────────────

def init_gemini(api_key: str):
    """Configure the Gemini client with the provided API key."""
    st.session_state["_genai_client"] = genai.Client(api_key=api_key)


def _client() -> genai.Client:
    client = st.session_state.get("_genai_client")
    if client is None:
        raise RuntimeError("Gemini client not initialised. Please enter your API key in the sidebar.")
    return client


_SYSTEM_PROMPT = (
    "You are LifeLink AI — a compassionate and knowledgeable medical assistant specialising in "
    "blood and organ donation. Your role is to:\n"
    "1. Answer questions about blood type compatibility, organ donation eligibility, and the "
    "donation process clearly and accurately.\n"
    "2. Help users understand match results and what the scores mean.\n"
    "3. Provide empathetic guidance to both donors and recipients.\n"
    "4. Explain medical terms in simple language.\n"
    "5. Remind users that this platform is for informational/matching purposes only and that "
    "actual donation decisions must involve certified medical professionals.\n\n"
    "Always be kind, factual, and non-alarmist. Never give specific clinical advice or diagnoses. "
    "Keep responses concise (under 300 words unless a detailed explanation is explicitly requested)."
)


# ── Context-aware chat ────────────────────────────────────────────────────────

def chat_with_context(user_message: str, history: list[dict]) -> str:
    """
    Send a message to Gemini with the full conversation history.
    history = list of {role: "user"|"assistant", content: str}
    Retries automatically on 503 / 429 transient errors.
    """
    last_err = None
    for attempt in range(_MAX_RETRIES):
        try:
            client = _client()

            contents = []
            for msg in history:
                role = "user" if msg["role"] == "user" else "model"
                contents.append(types.Content(role=role, parts=[types.Part(text=msg["content"])]))
            contents.append(types.Content(role="user", parts=[types.Part(text=user_message)]))

            response = client.models.generate_content(
                model=GEMINI_MODEL,
                contents=contents,
                config=types.GenerateContentConfig(system_instruction=_SYSTEM_PROMPT),
            )
            return response.text
        except Exception as e:
            last_err = e
            msg = str(e)
            if ("503" in msg or "UNAVAILABLE" in msg or "429" in msg or "quota" in msg.lower()) \
                    and attempt < _MAX_RETRIES - 1:
                time.sleep(_RETRY_DELAYS[attempt])
                continue
            break
    return f"⚠️ AI Error: {str(last_err)}\n\nPlease check your Gemini API key in the sidebar."


# ── One-shot utilities ────────────────────────────────────────────────────────

def _generate(prompt: str) -> str:
    """Single-turn generation helper with automatic retry on 503."""
    last_err = None
    for attempt in range(_MAX_RETRIES):
        try:
            client = _client()
            response = client.models.generate_content(
                model=GEMINI_MODEL,
                contents=prompt,
                config=types.GenerateContentConfig(system_instruction=_SYSTEM_PROMPT),
            )
            return response.text
        except Exception as e:
            last_err = e
            msg = str(e)
            # Only retry on transient server errors (503 / 429 rate-limit)
            if ("503" in msg or "UNAVAILABLE" in msg or "429" in msg or "quota" in msg.lower()) \
                    and attempt < _MAX_RETRIES - 1:
                time.sleep(_RETRY_DELAYS[attempt])
                continue
            break
    return f"Could not generate response: {last_err}"


def explain_match(match_result: dict) -> str:
    """Generate a human-readable explanation for a match result."""
    donor   = match_result["donor"]
    recip   = match_result["recipient"]
    score   = match_result["total_score"]
    reasons = "\n".join(f"  • {r}" for r in match_result["reasons"])

    prompt = (
        "A donor-recipient match has been found on the LifeLink platform. Please write a short, "
        "warm, and informative explanation (2–3 sentences) for the medical coordinator reviewing "
        "this match. Include what makes this a good (or acceptable) match.\n\n"
        f"Donor:     {donor['name']}, Blood type {donor['blood_type']}, "
        f"located in {donor['city']}, {donor['state']}\n"
        f"Recipient: {recip['name']}, Blood type {recip['blood_type']}, "
        f"needs {recip.get('organ_needed') or 'blood'}, urgency: {recip['urgency']}\n"
        f"Match score: {score}/100\n\n"
        f"Matching factors:\n{reasons}"
    )
    return _generate(prompt)


def suggest_next_steps(recipient: dict, top_match: dict | None) -> str:
    """Provide actionable next steps for a recipient given their best match."""
    if top_match:
        donor = top_match["donor"]
        context = (
            f"The best match found is donor {donor['name']} (Blood: {donor['blood_type']}, "
            f"City: {donor['city']}, {donor['state']}) with a compatibility score of "
            f"{top_match['total_score']}/100."
        )
    else:
        context = "No compatible donor has been found yet."

    prompt = (
        f"A patient named {recipient['name']} (Blood type {recipient['blood_type']}) urgently needs "
        f"{recipient.get('organ_needed') or 'a blood transfusion'} (urgency: {recipient['urgency']}). "
        f"They are at {recipient.get('hospital', 'a hospital')} in {recipient['city']}, {recipient['state']}.\n\n"
        f"{context}\n\n"
        "Please provide 3 concise, practical next steps the hospital coordinator should take right now. "
        "Be clear and actionable. Do not include disclaimers about not being a doctor."
    )
    return _generate(prompt)


def analyse_donor_profile(donor: dict) -> str:
    """Provide a brief AI-generated profile analysis for a donor."""
    organs = ", ".join(donor.get("organs") or []) or "N/A"
    prompt = (
        "Analyse this organ/blood donor profile briefly (2-3 sentences) for a matching coordinator. "
        "Highlight any notable compatibility advantages and flag any considerations.\n\n"
        f"Donor: {donor['name']}, Age: {donor['age']}, Gender: {donor['gender']}\n"
        f"Blood type: {donor['blood_type']}, Donation type: {donor['donation_type']}\n"
        f"Organs registered: {organs}\n"
        f"Location: {donor['city']}, {donor['state']}\n"
        f"Medical notes: {donor.get('medical_notes') or 'None provided'}"
    )
    return _generate(prompt)


def triage_urgency(medical_notes: str, stated_urgency: str) -> str:
    """AI-assisted urgency triage based on medical notes."""
    prompt = (
        f'A recipient has been registered with urgency level "{stated_urgency}". '
        f'Their medical notes say: "{medical_notes}"\n\n'
        "Based solely on the notes provided, does the stated urgency level seem appropriate? "
        "Reply in 1-2 sentences, noting if the urgency should potentially be escalated or "
        "if it seems consistent. Be conservative — err on the side of higher urgency."
    )
    return _generate(prompt)
