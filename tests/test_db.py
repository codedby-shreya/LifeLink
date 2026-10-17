import pytest

from utils import auth, db
from utils.auth import PermissionDenied


def donor_args(**kw):
    base = dict(name="Ravi Kumar", age=30, gender="Male", blood_type="O-", donation_type="Blood",
                organs=[], city="Patna", state="Bihar", phone="+91 98765 43210", email="r@example.com",
                medical_notes="private note")
    base.update(kw)
    return base


def req_args(**kw):
    base = dict(name="Priya Sharma", age=40, gender="Female", blood_type="A+", need_type="Blood",
                organ_needed="", city="Patna", state="Bihar", hospital="AIIMS Patna",
                phone="+91 91234 56789", email="", urgency="Urgent (1–3 days)", medical_notes="surgery")
    base.update(kw)
    return base


def test_donor_persists_and_is_public_safe(backend, anon):
    d = db.add_donor(**donor_args())
    assert d["id"].startswith("LL-D-") and len(d["access_code"]) == 9
    rows = db.get_donors()
    assert len(rows) == 1 and rows[0]["id"] == d["id"]
    for private in ("name", "phone", "email", "medical_notes", "age"):
        assert private not in rows[0]
    assert rows[0]["available"] is True and rows[0]["organs"] == []


def test_private_reads_require_admin(backend, anon):
    db.add_donor(**donor_args())
    with pytest.raises(PermissionDenied):
        db.get_donors(include_private=True)
    with pytest.raises(PermissionDenied):
        db.get_matches()
    with pytest.raises(PermissionDenied):
        db.donors_to_df()
    with pytest.raises(PermissionDenied):
        db.delete_record("donor", "x")
    with pytest.raises(PermissionDenied):
        db.update_match_status("x", "Contacted")
    with pytest.raises(PermissionDenied):
        db.update_donor_availability("x", False)
    with pytest.raises(PermissionDenied):
        db.update_recipient_status("x", "Cancelled")
    with pytest.raises(PermissionDenied):
        db.get_audit_log()


def test_admin_sees_private_fields(backend, admin):
    db.add_donor(**donor_args())
    row = db.get_donors(include_private=True)[0]
    assert row["name"] == "Ravi Kumar" and row["phone"].endswith("43210")


def test_duplicate_donor_phone_blocked(backend, anon):
    db.add_donor(**donor_args())
    with pytest.raises(db.DuplicateError) as e:
        db.add_donor(**donor_args(name="Someone Else", phone="9876543210"))
    assert e.value.kind == "donor"
    assert len(db.get_donors()) == 1


def test_resubmit_key_blocks_double_submit(backend, anon):
    db.add_donor(**donor_args(), submit_key="abc")
    with pytest.raises(db.DuplicateError) as e:
        db.add_donor(**donor_args(phone="9000000001"), submit_key="abc")
    assert e.value.kind == "resubmit"
    db.add_recipient(**req_args(), submit_key="r1")
    with pytest.raises(db.DuplicateError):
        db.add_recipient(**req_args(name="Other Person"), submit_key="r1")


def test_duplicate_active_request_blocked(backend, anon):
    db.add_recipient(**req_args())
    with pytest.raises(db.DuplicateError) as e:
        db.add_recipient(**req_args())
    assert e.value.kind == "request"


def test_organ_donor_requires_organs(backend, anon):
    with pytest.raises(ValueError):
        db.add_donor(**donor_args(donation_type="Organ", organs=[]))
    d = db.add_donor(**donor_args(donation_type="Organ", organs=["Kidney"]))
    assert d["organs"] == ["Kidney"]


def test_availability_self_service_and_code_check(backend, anon):
    d = db.add_donor(**donor_args())
    assert db.set_my_availability(d["id"], "WRONG-CODE", False) is False
    assert db.get_donors()[0]["available"] is True
    assert db.set_my_availability(d["id"], d["access_code"].lower(), False) is True
    assert db.get_donors()[0]["available"] is False
    assert db.get_donors(available_only=True) == []


def test_access_code_lockout(backend, anon):
    d = db.add_donor(**donor_args())
    for _ in range(auth.MAX_FAILURES):
        assert db.verify_access("donor", d["id"], "BAD0-BAD0") is False
    with pytest.raises(PermissionError):
        db.verify_access("donor", d["id"], d["access_code"])


def test_request_tracking_and_status_rules(backend, anon):
    r = db.add_recipient(**req_args())
    assert db.get_my_request(r["id"], "NOPE-NOPE") is None
    mine = db.get_my_request(r["id"], r["access_code"])
    assert mine["status"] == "Open" and mine["saved_matches"] == 0
    with pytest.raises(ValueError):
        db.set_my_request_status(r["id"], r["access_code"], "In Progress")
    assert db.set_my_request_status(r["id"], r["access_code"], "Cancelled") is True
    assert db.get_my_request(r["id"], r["access_code"])["status"] == "Cancelled"
    assert db.get_recipients(open_only=True) == []


def test_recipient_public_records_hide_private_data(backend, anon):
    db.add_recipient(**req_args())
    row = db.get_recipients()[0]
    for private in ("name", "phone", "email", "hospital", "medical_notes"):
        assert private not in row


def test_matches_persist_dedupe_and_status(backend, anon, admin):
    d = db.add_donor(**donor_args())
    r = db.add_recipient(**req_args())
    m = db.save_match(d["id"], r["id"], 87.46, {"reasons": ["x"], "blood_score": 80.0})
    assert m["created"] is True and m["score"] == 87.5
    again = db.save_match(d["id"], r["id"], 10, {})
    assert again["created"] is False and again["id"] == m["id"] and again["score"] == 87.5
    rows = db.get_matches()
    assert len(rows) == 1 and rows[0]["details"]["blood_score"] == 80.0
    assert rows[0]["donor_phone"].endswith("43210") and rows[0]["status"] == "Pending Contact"
    db.update_match_status(m["id"], "Completed")
    assert db.get_matches()[0]["status"] == "Completed"
    stats = db.get_public_stats()
    assert stats["successful_matches"] == 1 and stats["total_matches"] == 1
    df = db.matches_to_df()
    assert list(df["Status"]) == ["Completed"]


def test_cannot_match_unavailable_donor_or_closed_request(backend, anon, admin):
    d = db.add_donor(**donor_args())
    r = db.add_recipient(**req_args())
    db.update_donor_availability(d["id"], False)
    with pytest.raises(ValueError):
        db.save_match(d["id"], r["id"], 80, {})
    db.update_donor_availability(d["id"], True)
    db.update_recipient_status(r["id"], "Cancelled")
    with pytest.raises(ValueError):
        db.save_match(d["id"], r["id"], 80, {})


def test_stats_zero_state_and_counts(backend, anon):
    s = db.get_public_stats()
    assert s["total_donors"] == 0 and s["total_requests"] == 0 and s["successful_matches"] == 0
    db.add_donor(**donor_args())
    db.add_recipient(**req_args())
    s = db.get_public_stats()
    assert (s["total_donors"], s["available_donors"], s["total_requests"], s["open_requests"]) == (1, 1, 1, 1)
    assert db.donor_blood_counts()["O-"] == 1


def test_delete_cascades_and_is_audited(backend, admin):
    d = db.add_donor(**donor_args())
    r = db.add_recipient(**req_args())
    db.save_match(d["id"], r["id"], 80, {})
    db.delete_record("donor", d["id"])
    assert db.get_matches() == [] and db.get_donors() == []
    with pytest.raises(db.NotFoundError):
        db.delete_record("donor", d["id"])
    assert any(a["action"] == "donor.delete" for a in db.get_audit_log())


def test_data_survives_restart(backend, anon):
    """A fresh connection pool (≈ app restart) still sees the data."""
    from utils import database
    db.add_donor(**donor_args())
    database.reset_connections()
    assert len(db.get_donors()) == 1


def test_matching_algorithm_uses_database_records(backend, anon):
    from utils.matching import match_donors_to_recipient
    db.add_donor(**donor_args(blood_type="O-"))
    db.add_donor(**donor_args(phone="9000000002", blood_type="B+", city="Delhi", state="Delhi"))
    db.add_recipient(**req_args(blood_type="A+"))
    recip = db.get_recipients(open_only=True)[0]
    results = match_donors_to_recipient(recip, db.get_donors(available_only=True))
    assert len(results) == 1 and results[0]["donor"]["blood_type"] == "O-"
    assert results[0]["total_score"] == 40 * 0.8 + 30 * 1.0 + 20 * 0.75 + 10
