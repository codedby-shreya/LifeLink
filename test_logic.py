"""Quick logic test for matching algorithm (no Streamlit required)."""
import sys, types

# Mock streamlit before importing utils
st_mock = types.ModuleType("streamlit")
st_mock.session_state = {}
sys.modules["streamlit"] = st_mock

from config.constants import BLOOD_COMPATIBILITY, ALL_BLOOD_TYPES, GEMINI_MODEL, APP_TITLE
print("config.constants OK")

from utils.matching import blood_score, location_score, urgency_score, match_donors_to_recipient
print("utils.matching OK")

# --- blood_score tests ---
s, r = blood_score("O-", "A+")
assert s == 0.8, f"Expected 0.8 got {s}"
print(f"blood_score O- -> A+: {s}  PASS")

s, r = blood_score("B+", "A+")
assert s == 0.0, f"Expected 0.0 got {s}"
print(f"blood_score B+ -> A+: {s}  PASS (incompatible)")

s, r = blood_score("A+", "A+")
assert s == 1.0
print(f"blood_score A+ -> A+: {s}  PASS (exact)")

# --- location_score tests ---
donor_same_city = {"city": "Delhi", "state": "Delhi"}
recip = {"city": "Delhi", "state": "Delhi"}
l, _ = location_score(donor_same_city, recip)
assert l == 1.0
print(f"location_score same city: {l}  PASS")

donor_same_state = {"city": "Noida", "state": "Delhi"}
l2, _ = location_score(donor_same_state, recip)
assert l2 == 0.6
print(f"location_score same state: {l2}  PASS")

# --- match_donors_to_recipient test ---
donors = [
    {"id": "D1", "name": "Rahul", "age": 28, "gender": "Male",
     "blood_type": "O-", "donation_type": "Blood", "organs": [],
     "city": "Delhi", "state": "Delhi", "phone": "9999",
     "email": "", "medical_notes": "", "available": True},
    {"id": "D2", "name": "Sneha", "age": 32, "gender": "Female",
     "blood_type": "AB+", "donation_type": "Blood", "organs": [],
     "city": "Mumbai", "state": "Maharashtra", "phone": "8888",
     "email": "", "medical_notes": "", "available": True},
]
recipient = {
    "id": "R1", "name": "Amit", "age": 45, "gender": "Male",
    "blood_type": "A+", "need_type": "Blood", "organ_needed": "",
    "city": "Delhi", "state": "Delhi",
    "urgency": "Critical (< 24 hrs)", "hospital": "AIIMS",
    "phone": "7777", "email": "", "medical_notes": "",
}

results = match_donors_to_recipient(recipient, donors)
print(f"Matches for A+ recipient: {len(results)} (expected 1)")
assert len(results) == 1, f"Expected 1, got {len(results)}"
assert results[0]["donor"]["name"] == "Rahul", "O- donor should match A+ recipient"
print(f"Top match: {results[0]['donor']['name']} score={results[0]['total_score']}  PASS")

# AB+ is universal recipient — should match O-
recip_ab = dict(recipient)
recip_ab["blood_type"] = "AB+"
results2 = match_donors_to_recipient(recip_ab, donors)
print(f"Matches for AB+ recipient: {len(results2)} (expected 2)")
assert len(results2) == 2, f"Expected 2, got {len(results2)}"
print("All matching logic tests PASSED")
