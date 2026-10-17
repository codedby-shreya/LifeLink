"""Real-PostgreSQL checks of the Supabase security model (needs `pip install pgserver`)."""
import sqlite3
from pathlib import Path

import pytest

pytest.importorskip("pgserver")
psycopg = pytest.importorskip("psycopg")

SCHEMA = (Path(__file__).resolve().parent.parent / "db" / "schema.sql").read_text(encoding="utf-8")


@pytest.fixture()
def pg(_pg_server):
    with psycopg.connect(_pg_server.get_uri(), autocommit=True) as c:
        c.execute("drop schema public cascade; create schema public;")
        for role in ("anon", "authenticated", "lifelink_app"):
            c.execute(f"drop role if exists {role}")
            c.execute(f"create role {role} nologin")
        c.execute("grant usage on schema public to anon, authenticated")
        c.execute("alter default privileges in schema public grant all on tables to anon, authenticated")  # Supabase default
        c.execute(SCHEMA)
        c.execute(SCHEMA)  # idempotent: second run must not fail
        yield c


def as_role(conn, role, sql):
    conn.execute(f"set role {role}")
    try:
        cur = conn.execute(sql)
        return cur.fetchall() if cur.description else cur.rowcount
    finally:
        conn.execute("reset role")


def test_rls_enabled_on_every_table(pg):
    rows = pg.execute("select relname, relrowsecurity from pg_class where relnamespace = 'public'::regnamespace "
                      "and relkind = 'r'").fetchall()
    assert rows and all(enabled for _, enabled in rows), rows


@pytest.mark.parametrize("role", ["anon", "authenticated"])
@pytest.mark.parametrize("table", ["donors", "recipients", "matches", "audit_log", "auth_attempts"])
def test_public_supabase_roles_have_no_access(pg, role, table):
    with pytest.raises(psycopg.errors.InsufficientPrivilege):
        as_role(pg, role, f"select * from {table}")
    with pytest.raises(psycopg.errors.InsufficientPrivilege):
        as_role(pg, role, f"delete from {table}")


def test_app_role_can_work_but_cannot_change_schema(pg):
    pg.execute("""insert into donors (id, public_id, name, age, gender, blood_type, donation_type, city, state,
        phone, phone_norm, access_code_hash, consent_at) values (gen_random_uuid(), 'LL-D-TEST0001', 'Test Donor', 30,
        'Male', 'O+', 'Blood', 'Patna', 'Bihar', '9876543210', '9876543210', 'x', now())""")
    assert as_role(pg, "lifelink_app", "select count(*) from donors")[0][0] == 1
    as_role(pg, "lifelink_app", "update donors set available = false")
    pg.execute("set role lifelink_app")
    with pytest.raises(psycopg.errors.InsufficientPrivilege):
        pg.execute("drop table donors")
    with pytest.raises(psycopg.errors.InsufficientPrivilege):
        pg.execute("update audit_log set detail = 'tampered'")     # audit log is append-only
    with pytest.raises(psycopg.errors.InsufficientPrivilege):
        pg.execute("delete from audit_log")
    pg.execute("reset role")


def test_check_constraints_reject_bad_data(pg):
    with pytest.raises(psycopg.errors.CheckViolation):
        pg.execute("""insert into donors (id, public_id, name, age, gender, blood_type, donation_type, city, state,
            phone, phone_norm, access_code_hash, consent_at) values (gen_random_uuid(), 'LL-D-BAD00001', 'Kid', 12,
            'Male', 'O+', 'Blood', 'Patna', 'Bihar', '9876543210', '9876543210', 'x', now())""")


def test_sqlite_and_postgres_schemas_have_same_columns(pg, tmp_path, monkeypatch):
    from utils import database
    monkeypatch.setenv("SQLITE_PATH", str(tmp_path / "p.db"))
    monkeypatch.delenv("DATABASE_URL", raising=False)
    database.ensure_schema()
    lite = sqlite3.connect(tmp_path / "p.db")
    for table in ("donors", "recipients", "matches", "audit_log", "auth_attempts"):
        lite_cols = {r[1] for r in lite.execute(f"pragma table_info({table})")}
        pg_cols = {r[0] for r in pg.execute(
            "select column_name from information_schema.columns where table_schema='public' and table_name=%s", (table,))}
        assert lite_cols == pg_cols, (table, lite_cols ^ pg_cols)
