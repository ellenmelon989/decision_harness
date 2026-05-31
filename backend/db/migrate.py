"""Apply backend/db/migrations.sql to the Supabase Postgres database.

Reads SUPABASE_DB_URL from backend/.env. Get it from the Supabase dashboard →
Project Settings → Database → Connection string → URI (it contains the DB
password). Uses psql so the multi-statement DDL + DO/policy blocks run cleanly.

    python -m backend.db.migrate
"""
import os
import shutil
import subprocess
import sys
from pathlib import Path

from dotenv import load_dotenv


def main() -> None:
    load_dotenv(Path(__file__).resolve().parents[1] / ".env")  # backend/.env
    url = os.environ.get("SUPABASE_DB_URL")
    if not url:
        sys.exit("Set SUPABASE_DB_URL in backend/.env "
                 "(Supabase → Settings → Database → Connection string → URI).")
    psql = shutil.which("psql")
    if not psql:
        sys.exit("psql not found. `brew install postgresql`, or paste migrations.sql "
                 "into the Supabase SQL editor instead.")
    sql = Path(__file__).resolve().parent / "migrations.sql"
    print(f"Applying {sql.name} → Supabase …")
    subprocess.run([psql, url, "-v", "ON_ERROR_STOP=1", "-f", str(sql)], check=True)
    print("✓ migrations applied")


if __name__ == "__main__":
    main()
