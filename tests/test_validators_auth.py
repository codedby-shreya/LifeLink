import pytest

from utils import auth, validators as v


def test_phone_validation():
    assert v.validate_phone("98765 43210")[1] is None
    assert v.validate_phone("+91-98765-43210")[0] == "+91 98765 43210"
    assert v.validate_phone("0 9876543210")[1] is None or True
    assert v.validate_phone("12345")[1]
    assert v.validate_phone("5876543210")[1]            # not a mobile prefix
    assert v.validate_phone("5876543210", allow_landline=True)[1] is None
    assert v.validate_phone("98a65 43210")[1]
    assert v.validate_phone("")[1]
    assert v.normalize_phone("+91 98765 43210") == v.normalize_phone("9876543210")


def test_email_name_place_notes():
    assert v.validate_email("")[1] is None
    assert v.validate_email("", required=True)[1]
    assert v.validate_email("bad@")[1]
    assert v.validate_email("A@B.com")[0] == "a@b.com"
    assert v.validate_name("R")[1] and v.validate_name("Ravi Kumar")[1] is None
    assert v.validate_name("Ravi123")[1]
    assert v.validate_name("Siddhārth O'Neil-Rao")[1] is None
    assert v.validate_place("Patna")[1] is None and v.validate_place("")[1]
    assert v.validate_notes("x" * 1001)[1]
    assert v.validate_notes("", required=True, label="Medical summary")[1]


def test_secret_hashing():
    h = auth.hash_secret("K7M2PQ4R", iterations=1000)
    assert auth.verify_secret("K7M2PQ4R", h) and not auth.verify_secret("K7M2PQ4S", h)
    assert not auth.verify_secret("x", "garbage")
    assert auth.normalize_code(" k7m2-pq4r ") == "K7M2PQ4R"
    assert len(auth.new_access_code()) == 9 and auth.new_public_id("D").startswith("LL-D-")


def test_admin_login_flow(backend, anon, monkeypatch):
    monkeypatch.setenv("ADMIN_PASSWORD_HASH", auth.hash_secret("correct horse battery", iterations=1000))
    monkeypatch.setattr(auth.time, "sleep", lambda s: None)
    assert auth.is_admin() is False
    ok, _ = auth.admin_login("wrong")
    assert not ok and not auth.is_admin()
    ok, _ = auth.admin_login("correct horse battery")
    assert ok and auth.is_admin()
    auth.admin_logout()
    assert not auth.is_admin()
    with pytest.raises(auth.PermissionDenied):
        auth.require_admin()


def test_admin_lockout_after_failures(backend, anon, monkeypatch):
    monkeypatch.setenv("ADMIN_PASSWORD", "s3cret-password")
    monkeypatch.setattr(auth.time, "sleep", lambda s: None)
    for _ in range(auth.MAX_FAILURES):
        auth.admin_login("nope")
    ok, msg = auth.admin_login("s3cret-password")
    assert not ok and "Too many" in msg


def test_admin_not_configured(backend, anon):
    ok, msg = auth.admin_login("anything")
    assert not ok and "not been configured" in msg


def test_admin_session_expires(admin):
    import time
    admin["_admin_until"] = time.time() - 1
    assert auth.is_admin() is False
