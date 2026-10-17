"""
Database connection layer for LifeLink.

* Production: PostgreSQL (Supabase) through a small psycopg connection pool.
  Configure with DATABASE_URL (environment variable or Streamlit secret).
* Local development / tests: SQLite file, used automatically when DATABASE_URL
  is not set (or when DB_BACKEND=sqlite).

This module knows nothing about donors, requests or matching — it only offers
`transaction()` (a context manager yielding an object with query/one/execute)
plus schema checks. SQL elsewhere is written with %s placeholders and is
always parameterised; the SQLite adapter translates the placeholder style.
"""

from __future__ import annotations

import contextlib
import datetime as dt
import json
import logging
import os
import sqlite3
import threading
from pathlib import Path
from typing import Any, Iterator, Sequence

log = logging.getLogger("lifelink.db")

ROOT = Path(__file__).resolve().parent.parent
SCHEMA_VERSION = 1


# ── Exceptions ───────────────────────────────────────────────────────────────

class DatabaseUnavailable(RuntimeError):
    """The database cannot be reached or is not configured."""


class SchemaMissing(DatabaseUnavailable):
    """Connected, but the LifeLink tables have not been created yet."""


class UniqueViolation(Exception):
    """A UNIQUE constraint was violated (backend-neutral)."""

    def __init__(self, detail: str = ""):
        super().__init__(detail)
        self.detail = detail


# ── Settings ─────────────────────────────────────────────────────────────────

def get_setting(name: str, default: str = "") -> str:
    """Environment variable first, then Streamlit secrets. Never logs values."""
    value = os.environ.get(name)
    if value:
        return value
    try:
        import streamlit as st  # imported lazily so this module works in scripts/tests

        secret = st.secrets.get(name, "")
        if secret:
            return str(secret)
    except Exception:
        pass
    return default


def backend_name() -> str:
    explicit = get_setting("DB_BACKEND").strip().lower()
    if explicit in ("postgres", "sqlite"):
        return explicit
    return "postgres" if get_setting("DATABASE_URL") else "sqlite"


def sqlite_path() -> Path:
    raw = get_setting("SQLITE_PATH") or "data/lifelink.db"
    path = Path(raw)
    return path if path.is_absolute() else ROOT / path


def utcnow() -> dt.datetime:
    return dt.datetime.now(dt.timezone.utc).replace(microsecond=0)


# ── Transaction wrapper ──────────────────────────────────────────────────────

class _Tx:
    """Thin uniform wrapper over a psycopg or sqlite3 connection."""

    def __init__(self, conn: Any, backend: str):
        self._conn = conn
        self.backend = backend

    # -- parameter adaptation --------------------------------------------------
    def json(self, obj: Any) -> Any:
        if self.backend == "postgres":
            from psycopg.types.json import Jsonb

            return Jsonb(obj)
        return json.dumps(obj, ensure_ascii=False)

    def _adapt(self, params: Sequence[Any]) -> tuple:
        if self.backend == "postgres":
            return tuple(params)
        out = []
        for p in params:
            if isinstance(p, dt.datetime):
                p = p.astimezone(dt.timezone.utc).isoformat(timespec="seconds")
            elif isinstance(p, bool):
                p = int(p)
            out.append(p)
        return tuple(out)

    # -- execution -------------------------------------------------------------
    def _run(self, sql: str, params: Sequence[Any]):
        try:
            if self.backend == "postgres":
                import psycopg.errors as pgerr

                cur = self._conn.cursor()
                try:
                    cur.execute(sql, self._adapt(params))
                except pgerr.UniqueViolation as exc:
                    raise UniqueViolation(str(exc)) from exc
                return cur
            cur = self._conn.execute(sql.replace("%s", "?"), self._adapt(params))
            return cur
        except sqlite3.IntegrityError as exc:
            raise UniqueViolation(str(exc)) from exc

    def query(self, sql: str, params: Sequence[Any] = ()) -> list[dict]:
        cur = self._run(sql, params)
        if self.backend == "postgres":
            rows = cur.fetchall() if cur.description else []
            cur.close()
            return [dict(r) for r in rows]
        return [dict(r) for r in cur.fetchall()]

    def one(self, sql: str, params: Sequence[Any] = ()) -> dict | None:
        rows = self.query(sql, params)
        return rows[0] if rows else None

    def execute(self, sql: str, params: Sequence[Any] = ()) -> int:
        cur = self._run(sql, params)
        count = cur.rowcount
        if self.backend == "postgres":
            cur.close()
        return count


# ── Postgres pool ────────────────────────────────────────────────────────────

_pool_lock = threading.Lock()
_pool: Any = None


def _pg_pool():
    global _pool
    with _pool_lock:
        if _pool is None:
            url = get_setting("DATABASE_URL")
            if not url:
                raise DatabaseUnavailable("DATABASE_URL is not configured.")
            try:
                from psycopg.rows import dict_row
                from psycopg_pool import ConnectionPool
            except ImportError as exc:  # pragma: no cover
                raise DatabaseUnavailable("psycopg / psycopg_pool are not installed.") from exc
            pool = ConnectionPool(
                url,
                min_size=1,
                max_size=5,
                open=False,
                timeout=float(get_setting("DB_POOL_TIMEOUT", "10") or 10),
                check=ConnectionPool.check_connection,
                kwargs={
                    "row_factory": dict_row,
                    "prepare_threshold": None,  # required for Supabase's transaction pooler
                    "connect_timeout": 8,
                },
            )
            pool.open(wait=False)
            _pool = pool
        return _pool


def reset_connections() -> None:
    """Close the pool (used by tests and by the 'retry' button after an outage)."""
    global _pool
    with _pool_lock:
        if _pool is not None:
            try:
                _pool.close()
            except Exception:  # pragma: no cover
                pass
            _pool = None


@contextlib.contextmanager
def transaction() -> Iterator[_Tx]:
    """
    Run a block of SQL atomically. Commits on success, rolls back on error.
    Raises DatabaseUnavailable when the server cannot be reached.
    """
    if backend_name() == "postgres":
        try:
            import psycopg
            from psycopg_pool import PoolTimeout
        except ImportError as exc:  # pragma: no cover
            raise DatabaseUnavailable("psycopg is not installed.") from exc
        try:
            wait = float(get_setting("DB_POOL_TIMEOUT", "10") or 10)
            with _pg_pool().connection(timeout=wait) as conn:
                yield _Tx(conn, "postgres")
        except (psycopg.OperationalError, PoolTimeout) as exc:
            log.error("Postgres unavailable: %s", type(exc).__name__)
            raise DatabaseUnavailable("The database is temporarily unreachable.") from exc
        return

    path = sqlite_path()
    try:
        path.parent.mkdir(parents=True, exist_ok=True)
        conn = sqlite3.connect(path, timeout=10)
    except (OSError, sqlite3.Error) as exc:
        raise DatabaseUnavailable(f"Cannot open the local SQLite database: {exc}") from exc
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    try:
        conn.execute("PRAGMA journal_mode = WAL")
    except sqlite3.Error:  # pragma: no cover
        pass
    try:
        yield _Tx(conn, "sqlite")
        conn.commit()
    except sqlite3.OperationalError as exc:
        conn.rollback()
        raise DatabaseUnavailable(f"SQLite error: {exc}") from exc
    except BaseException:
        conn.rollback()
        raise
    finally:
        conn.close()


# ── Schema ───────────────────────────────────────────────────────────────────

_SQLITE_SCHEMA = """
CREATE TABLE IF NOT EXISTS schema_migrations (
    version INTEGER PRIMARY KEY, applied_at TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS donors (
    id TEXT PRIMARY KEY, public_id TEXT NOT NULL UNIQUE,
    name TEXT NOT NULL CHECK (length(name) BETWEEN 2 AND 80),
    age INTEGER NOT NULL CHECK (age BETWEEN 18 AND 65),
    gender TEXT NOT NULL CHECK (gender IN ('Male','Female','Other')),
    blood_type TEXT NOT NULL CHECK (blood_type IN ('A+','A-','B+','B-','AB+','AB-','O+','O-')),
    donation_type TEXT NOT NULL CHECK (donation_type IN ('Blood','Organ')),
    organs TEXT NOT NULL DEFAULT '[]',
    city TEXT NOT NULL CHECK (length(city) BETWEEN 2 AND 60),
    state TEXT NOT NULL, phone TEXT NOT NULL, phone_norm TEXT NOT NULL,
    email TEXT NOT NULL DEFAULT '',
    medical_notes TEXT NOT NULL DEFAULT '' CHECK (length(medical_notes) <= 1000),
    available INTEGER NOT NULL DEFAULT 1,
    access_code_hash TEXT NOT NULL, submit_key TEXT UNIQUE,
    consent_at TEXT NOT NULL, registered_at TEXT NOT NULL, updated_at TEXT NOT NULL
);
CREATE UNIQUE INDEX IF NOT EXISTS donors_phone_norm_key ON donors (phone_norm);
CREATE INDEX IF NOT EXISTS donors_blood_idx ON donors (blood_type);
CREATE INDEX IF NOT EXISTS donors_state_city_idx ON donors (state, city);
CREATE INDEX IF NOT EXISTS donors_available_idx ON donors (available);

CREATE TABLE IF NOT EXISTS recipients (
    id TEXT PRIMARY KEY, public_id TEXT NOT NULL UNIQUE,
    name TEXT NOT NULL CHECK (length(name) BETWEEN 2 AND 80),
    age INTEGER NOT NULL CHECK (age BETWEEN 0 AND 120),
    gender TEXT NOT NULL CHECK (gender IN ('Male','Female','Other')),
    blood_type TEXT NOT NULL CHECK (blood_type IN ('A+','A-','B+','B-','AB+','AB-','O+','O-')),
    need_type TEXT NOT NULL CHECK (need_type IN ('Blood','Organ')),
    organ_needed TEXT NOT NULL DEFAULT '',
    city TEXT NOT NULL CHECK (length(city) BETWEEN 2 AND 60),
    state TEXT NOT NULL,
    hospital TEXT NOT NULL CHECK (length(hospital) BETWEEN 2 AND 120),
    phone TEXT NOT NULL, phone_norm TEXT NOT NULL, email TEXT NOT NULL DEFAULT '',
    urgency TEXT NOT NULL CHECK (urgency IN
        ('Critical (< 24 hrs)','Urgent (1–3 days)','Moderate (within a week)','Stable')),
    medical_notes TEXT NOT NULL DEFAULT '' CHECK (length(medical_notes) <= 1000),
    status TEXT NOT NULL DEFAULT 'Open'
        CHECK (status IN ('Open','In Progress','Fulfilled','Cancelled')),
    access_code_hash TEXT NOT NULL, submit_key TEXT UNIQUE,
    consent_at TEXT NOT NULL, posted_at TEXT NOT NULL, updated_at TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS recipients_status_idx ON recipients (status);
CREATE INDEX IF NOT EXISTS recipients_blood_idx ON recipients (blood_type);
CREATE INDEX IF NOT EXISTS recipients_phone_idx ON recipients (phone_norm);
CREATE INDEX IF NOT EXISTS recipients_posted_idx ON recipients (posted_at);

CREATE TABLE IF NOT EXISTS matches (
    id TEXT PRIMARY KEY, public_id TEXT NOT NULL UNIQUE,
    donor_id TEXT NOT NULL REFERENCES donors(id) ON DELETE CASCADE,
    recipient_id TEXT NOT NULL REFERENCES recipients(id) ON DELETE CASCADE,
    score REAL NOT NULL CHECK (score BETWEEN 0 AND 100),
    details TEXT NOT NULL DEFAULT '{}',
    status TEXT NOT NULL DEFAULT 'Pending Contact'
        CHECK (status IN ('Pending Contact','Contacted','In Progress','Completed','Failed')),
    matched_at TEXT NOT NULL, updated_at TEXT NOT NULL,
    UNIQUE (donor_id, recipient_id)
);
CREATE INDEX IF NOT EXISTS matches_status_idx ON matches (status);
CREATE INDEX IF NOT EXISTS matches_recipient_idx ON matches (recipient_id);
CREATE INDEX IF NOT EXISTS matches_matched_idx ON matches (matched_at);

CREATE TABLE IF NOT EXISTS audit_log (
    id TEXT PRIMARY KEY, at TEXT NOT NULL, actor TEXT NOT NULL DEFAULT 'admin',
    action TEXT NOT NULL, entity TEXT NOT NULL DEFAULT '',
    entity_id TEXT NOT NULL DEFAULT '', detail TEXT NOT NULL DEFAULT ''
);
CREATE INDEX IF NOT EXISTS audit_log_at_idx ON audit_log (at);

CREATE TABLE IF NOT EXISTS auth_attempts (
    id TEXT PRIMARY KEY, scope TEXT NOT NULL, success INTEGER NOT NULL,
    attempted_at TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS auth_attempts_scope_idx ON auth_attempts (scope, attempted_at);
"""

_REQUIRED_TABLES = ("donors", "recipients", "matches", "audit_log", "auth_attempts")


def ensure_schema() -> None:
    """
    SQLite: create tables automatically (never drops anything).
    Postgres: verify the tables exist; they are created by db/schema.sql so the
    app itself can run with a least-privilege role that cannot alter the schema.
    """
    if backend_name() == "sqlite":
        path = sqlite_path()
        try:
            path.parent.mkdir(parents=True, exist_ok=True)
            conn = sqlite3.connect(path, timeout=10)
        except (OSError, sqlite3.Error) as exc:
            raise DatabaseUnavailable(f"Cannot open the local SQLite database: {exc}") from exc
        try:
            conn.executescript(_SQLITE_SCHEMA)
            conn.execute(
                "INSERT OR IGNORE INTO schema_migrations (version, applied_at) VALUES (?, ?)",
                (SCHEMA_VERSION, utcnow().isoformat()),
            )
            conn.commit()
        finally:
            conn.close()
        return

    with transaction() as tx:
        missing = [
            t for t in _REQUIRED_TABLES
            if tx.one("select to_regclass(%s) as r", (f"public.{t}",))["r"] is None
        ]
    if missing:
        raise SchemaMissing(
            "Database tables are missing (" + ", ".join(missing) + "). "
            "Run db/schema.sql in the Supabase SQL editor — see README."
        )


def ping() -> bool:
    """True if the database answers a trivial query."""
    try:
        with transaction() as tx:
            tx.one("select 1 as ok")
        return True
    except DatabaseUnavailable:
        return False
