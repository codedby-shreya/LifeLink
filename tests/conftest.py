import os
import sys
import tempfile
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))


def _backends():
    params = ["sqlite"]
    try:
        import pgserver  # noqa: F401
        params.append("postgres")
    except ImportError:
        pass
    return params


@pytest.fixture(scope="session")
def _pg_server():
    pgserver = pytest.importorskip("pgserver")
    d = tempfile.mkdtemp()
    server = pgserver.get_server(d)
    yield server
    server.cleanup()


@pytest.fixture(params=_backends())
def backend(request, tmp_path, monkeypatch):
    """Runs each DB test against SQLite and (if pgserver is installed) a real PostgreSQL."""
    from utils import database
    database.reset_connections()
    for var in ("DATABASE_URL", "DB_BACKEND", "SQLITE_PATH", "ADMIN_PASSWORD", "ADMIN_PASSWORD_HASH"):
        monkeypatch.delenv(var, raising=False)
    if request.param == "sqlite":
        monkeypatch.setenv("SQLITE_PATH", str(tmp_path / "t.db"))
        database.ensure_schema()
    else:
        server = request.getfixturevalue("_pg_server")
        import psycopg
        url = server.get_uri()
        with psycopg.connect(url, autocommit=True) as c:
            c.execute("drop schema public cascade; create schema public;")
            c.execute((Path(__file__).resolve().parent.parent / "db" / "schema.sql").read_text(encoding="utf-8"))
        monkeypatch.setenv("DATABASE_URL", url)
        database.reset_connections()
        database.ensure_schema()
    yield request.param
    database.reset_connections()


@pytest.fixture
def admin(monkeypatch):
    """Pretend an administrator is signed in."""
    from utils import auth
    store = {}
    monkeypatch.setattr(auth, "_session", lambda: store)
    import time
    store["_admin_until"] = time.time() + 600
    return store


@pytest.fixture
def anon(monkeypatch):
    from utils import auth
    store = {}
    monkeypatch.setattr(auth, "_session", lambda: store)
    return store
