"""
Apply db/schema.sql to a PostgreSQL / Supabase database.

    python scripts/init_db.py --url "postgresql://postgres:...@db.xxxx.supabase.co:5432/postgres"

Use the ADMIN connection string (the 'postgres' user), not the lifelink_app one.
The script is idempotent and never drops data.
"""
import argparse
import os
import sys
from pathlib import Path

import psycopg

SCHEMA = Path(__file__).resolve().parent.parent / "db" / "schema.sql"


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--url", default=os.environ.get("DATABASE_ADMIN_URL", ""),
                        help="Admin connection string (or set DATABASE_ADMIN_URL)")
    args = parser.parse_args()
    if not args.url:
        print("Provide --url or set DATABASE_ADMIN_URL.", file=sys.stderr)
        return 2
    with psycopg.connect(args.url, autocommit=True) as conn:
        conn.execute(SCHEMA.read_text(encoding="utf-8"))
    print("Schema applied.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
