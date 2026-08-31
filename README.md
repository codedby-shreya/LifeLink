# 🩸 LifeLink — Blood & Organ Donor Matching Platform

An **AI-powered Streamlit application** that connects blood and organ donors with
recipients through intelligent compatibility matching, urgent request management, and
a conversational AI assistant powered by **Google Gemini**.

---

## Features

| Feature | Description |
|---|---|
| 🩺 Donor Registration | Register as a blood or organ donor with full profile |
| 🆘 Urgent Request Posting | Post time-critical recipient needs with urgency levels |
| 🔗 Matching Engine | Automatic scoring based on blood type, location & urgency |
| 🤖 AI Assistant | Gemini-powered chat for donation questions |
| 📊 Admin Dashboard | Analytics, charts, and match management |

---

## Matching Algorithm

Each donor–recipient pair is scored out of **100**:

| Factor | Weight | Details |
|---|---|---|
| 🩸 Blood type compatibility | 40% | Exact = 100, Compatible = 80, Incompatible = 0 (disqualified) |
| 📍 Geographic proximity | 30% | Same city = 100, Same state = 60, Different state = 20 |
| ⚡ Urgency level | 20% | Critical = 100, Urgent = 75, Moderate = 50, Stable = 25 |
| ✅ Donor availability | 10% | Available = 100 |

Score ≥ 80 → Strong match | 60–79 → Acceptable | < 60 → Review needed

---

## Quick Start

### 1. Clone & install

```bash
git clone <repo-url>
cd blood-organ-donor-matching
pip install -r requirements.txt
```

### 2. Get a Gemini API key

Visit [Google AI Studio](https://aistudio.google.com/app/apikey) — it's free.

### 3. Run

```bash
streamlit run app.py
```

### 4. Enter your API key

Paste your Gemini API key in the **sidebar** when the app opens.

---

## Project Structure

```
blood organ donor matching/
├── app.py                        # Main Streamlit entry point
├── requirements.txt
├── .env.example
├── config/
│   ├── __init__.py
│   └── constants.py              # Blood types, organs, weights, states
├── utils/
│   ├── __init__.py
│   ├── db.py                     # Session-state data store (CRUD)
│   ├── matching.py               # Scoring & matching algorithm
│   └── ai_helper.py              # Gemini AI wrappers
└── pages/
    ├── __init__.py
    ├── donor_registration.py
    ├── recipient_request.py
    ├── matching_engine.py
    ├── ai_assistant.py
    └── admin_dashboard.py
```

---

## Deployment on Streamlit Cloud

1. Push to a **public GitHub repository**.
2. Go to [share.streamlit.io](https://share.streamlit.io) → New app → select your repo.
3. Set `app.py` as the main file.
4. Add `GEMINI_API_KEY` as a **Secret** in the Streamlit Cloud settings
   (or enter it in the sidebar at runtime).

---

## Notes

- Data is stored in **Streamlit session state** — it resets on page refresh.
  For production persistence, swap `utils/db.py` with a SQLite / PostgreSQL backend.
- This platform is for **matching purposes only**. All actual donation decisions require
  certified medical professionals and proper laboratory testing.

---

## License

MIT
