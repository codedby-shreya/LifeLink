# LifeLink — *Care connects us all.*

Blood and organ donor matching for India, built with **Python + Streamlit**, persisted in **Supabase PostgreSQL**
(SQLite for local development), with a Gemini-powered assistant.

> LifeLink is a coordination tool. It does not give medical advice and never replaces emergency services (112) or
> the treating hospital. Match scores are software-generated and are **not** clinical approval.

## Features

| Page | What it does |
|---|---|
| **Home** | Live statistics from the database, how it works, blood-compatibility explorer, safety & privacy |
| **Become a Donor** | Validated registration, duplicate protection, private donor ID + access code, self-service availability |
| **Request Blood** | Request form, request ID + private tracking code, status tracking, anonymous open-requests list |
| **Find a Donor** | The original matching engine (unchanged weights) with filters, sorting, score breakdowns, *Save match* |
| **AI Assistant** | Gemini chat (same provider as before) with retry handling |
| **Admin Dashboard** | Password-protected: metrics, charts, donor / request / match management, audit log |

## Project structure

```
app.py                     entry point: config, theme, DB check, navigation
config/constants.py        blood rules, urgency & scoring weights (unchanged) + new constants
utils/matching.py          matching algorithm — UNCHANGED, no UI or DB code
utils/database.py          connection layer (Postgres pool / SQLite), schema check
utils/db.py                repository: all queries, privacy rules, admin checks
utils/auth.py              admin login, access-code hashing, throttling
utils/validators.py        input validation (phone, email, names, notes)
utils/ai_helper.py         Gemini calls (key from env/secrets, prompts without personal data)
utils/ui.py, utils/nav.py  design system (CSS + components) and page routing
views/                     one module per page
db/schema.sql              PostgreSQL schema + RLS + grants (idempotent, never drops data)
db/00_create_app_role.sql  least-privilege role for the app
scripts/                   init_db.py (apply schema), hash_password.py
tests/                     pytest suite;  test_logic.py = original matching tests
docs/legacy/               original slide deck and screenshots of the first version
```

## Run locally (SQLite — no setup)

```bash
python -m venv .venv && source .venv/bin/activate        # Windows: .venv\Scripts\activate
pip install -r requirements.txt
cp .env.example .env                                      # add GEMINI_API_KEY (optional)
python scripts/hash_password.py                           # paste the printed line into .env
streamlit run app.py
```

Without `DATABASE_URL` the app uses `data/lifelink.db` (git-ignored) and creates the tables itself.
Without `ADMIN_PASSWORD_HASH` the admin page stays locked (by design).
SQLite data is **not** shared or kept on Streamlit Cloud — use Supabase there.

## Supabase setup (production)

1. Create a project at supabase.com and note the database password.
2. **SQL Editor →** run `db/00_create_app_role.sql` after replacing the placeholder password (long and random).
3. **SQL Editor →** run `db/schema.sql`. (Or: `python scripts/init_db.py --url "<admin connection string>"`.)
   It creates the tables, indexes and constraints, turns on Row-Level Security, removes all access for Supabase's
   public `anon` / `authenticated` roles, and grants the app role only what it needs. Safe to re-run.
4. Get the connection string from Supabase's *Connect* panel and use the **pooler** host (Streamlit Cloud reaches
   the internet over IPv4; the direct host may be IPv6-only). Change the username to `lifelink_app.<project-ref>` and
   the password to the app role's password. URL-encode special characters in the password.
5. Put it in secrets as `DATABASE_URL` (below). **Never** use the `service_role` key anywhere in this app.

## Secrets

Local: `.env` or `.streamlit/secrets.toml`. Cloud: *App → Settings → Secrets*. See `.streamlit/secrets.toml.example`.

| Key | Purpose |
|---|---|
| `DATABASE_URL` | Supabase Postgres connection for the `lifelink_app` role |
| `ADMIN_PASSWORD_HASH` | PBKDF2 hash from `python scripts/hash_password.py` (`ADMIN_PASSWORD` plain text also works, not recommended) |
| `ADMIN_EMAIL` | Optional. If set, the admin must enter one of these emails (comma-separated) **and** the password |
| `GEMINI_API_KEY` | Google Gemini key for the assistant and AI notes (optional) |

## Deploy on Streamlit Community Cloud

1. Create a GitHub repository and push this folder. Check `git status` first — `.env`, `secrets.toml`
   and `data/*.db` must **not** appear (they are in `.gitignore`).
   ```bash
   git init && git add . && git commit -m "LifeLink" && git branch -M main
   git remote add origin https://github.com/<you>/lifelink.git && git push -u origin main
   ```
2. share.streamlit.io → **Create app** → pick the repo, branch `main`, main file `app.py`.
3. **Advanced settings → Secrets**: paste the three keys above. Deploy.
4. Open the app, register a test donor, redeploy/reboot, and confirm the donor is still there.

## How privacy and security work

* **Public pages never show** names, phone numbers, emails, patient names, hospital names or medical notes.
  Search results show donor/request ID, blood group, city/state, availability and score only.
* **Coordinators (admin)** see contact details in the dashboard to arrange introductions.
* **The Admin Dashboard link is hidden** from the sidebar for everyone except a signed-in admin. The admin signs in at
  `/admin` (e.g. `https://your-app.streamlit.app/admin`). Hiding the link is only convenience — the real protection is below.
* **Admin protection is server-side**: login with throttling, 30-minute idle timeout, and every private-data
  function in `utils/db.py` re-checks the admin session (hiding a page is not the control).
* **Donors / requesters** get a private ID + access code once; only a PBKDF2 hash is stored. Wrong codes are
  rate-limited per record.
* **Database**: parameterised SQL only; RLS on every table; public Supabase roles revoked; app role cannot alter
  schema and can only append to the audit log.
* **AI**: key stays server-side; prompts use IDs and clinical facts, never names or contact details.
  Chat history lives in the browser session only — it is not stored.
* Duplicate protection: unique phone per donor, one active request per patient/need, and a per-form submission key
  so double-clicks / refreshes cannot create twice.

## Tests

```bash
pip install -r requirements-dev.txt
python -m pytest            # DB tests run on SQLite and, if pgserver is installed, a real PostgreSQL
python test_logic.py        # original matching-logic checks
```

## Migrating old data

The first version kept donors and requests only in `st.session_state`, which disappears when the app restarts or the
browser tab closes, so there is no stored data to migrate. If you kept records elsewhere (spreadsheet, notes),
re-enter them through the **Become a Donor** and **Request Blood** forms: validation and duplicate checks apply.

## Known limitations

* No distance filter: records have city/state, not coordinates (filters are Anywhere / Same state / Same city).
* "Lives impacted" = requests marked *Fulfilled*; it is not an estimate of recipients per donation.
* Anyone can *Save match* for an open request and an available donor (it only creates a pending item for coordinators).
* Admin uses one shared password (optionally restricted by `ADMIN_EMAIL`); the email is a second check, not a verified
  email login, and there are no per-coordinator accounts. For multiple staff, add Supabase Auth or
  Streamlit's OIDC login.
* Admin tables load all records into memory — fine for thousands of rows, add pagination beyond that.
* The Inter font is loaded from Google Fonts; offline it falls back to system sans-serif.

## Troubleshooting

| Symptom | Fix |
|---|---|
| "Database setup needed" | Run `db/schema.sql` (and `00_create_app_role.sql` first). |
| "We can't reach the database" | Check `DATABASE_URL`, the pooler host, URL-encoding of the password; press *Try again*. |
| Admin page says it is switched off | Set `ADMIN_PASSWORD_HASH` in secrets and reboot the app. |
| Assistant says it is not available | Set `GEMINI_API_KEY`. Busy/quota errors show a *Try again* button. |
| Data disappears after redeploy | You are on SQLite. Set `DATABASE_URL`. |

**Website link** = https://lifelink-dyvtt99samukjdimfcxbvj.streamlit.app/
