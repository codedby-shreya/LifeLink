"""Create the ADMIN_PASSWORD_HASH value:  python scripts/hash_password.py"""
import getpass
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from utils.auth import hash_secret  # noqa: E402

pw = getpass.getpass("Admin password: ")
if len(pw) < 10:
    raise SystemExit("Use at least 10 characters.")
if pw != getpass.getpass("Repeat password: "):
    raise SystemExit("Passwords do not match.")
print("\nADMIN_PASSWORD_HASH = \"" + hash_secret(pw) + "\"")
