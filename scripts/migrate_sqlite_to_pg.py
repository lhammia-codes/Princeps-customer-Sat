import os
import sqlite3
import asyncio
import asyncpg
from datetime import datetime
from pathlib import Path
from dotenv import load_dotenv

BASE_DIR = Path(__file__).resolve().parent.parent
load_dotenv(BASE_DIR / ".env")

DATABASE_URL = os.getenv("DATABASE_URL")
SQLITE_DB_PATH = BASE_DIR / "cs_operations.db"

CREATE_TABLE_SQL = """
CREATE TABLE IF NOT EXISTS loan_assignments (
    loan_id TEXT PRIMARY KEY,
    relationship_manager TEXT NOT NULL,
    followup_status TEXT NOT NULL DEFAULT 'not contacted',
    notes TEXT,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);
CREATE INDEX IF NOT EXISTS idx_loan_assignments_rm ON loan_assignments(relationship_manager);
CREATE INDEX IF NOT EXISTS idx_loan_assignments_status ON loan_assignments(followup_status);
"""

def parse_dt(val):
    if not val:
        return datetime.now()
    if isinstance(val, datetime):
        return val
    try:
        return datetime.strptime(val, "%Y-%m-%d %H:%M:%S")
    except Exception:
        try:
            return datetime.fromisoformat(val)
        except Exception:
            return datetime.now()

async def migrate():
    if not SQLITE_DB_PATH.exists():
        print(f"SQLite DB not found at {SQLITE_DB_PATH}")
        return

    # Read from SQLite
    sqlite_conn = sqlite3.connect(SQLITE_DB_PATH)
    sqlite_cursor = sqlite_conn.cursor()
    sqlite_cursor.execute("SELECT loan_id, relationship_manager, followup_status, notes, updated_at FROM loan_assignments")
    sqlite_rows = sqlite_cursor.fetchall()
    sqlite_conn.close()

    print(f"Found {len(sqlite_rows)} records in SQLite.")

    # Connect to PostgreSQL
    pg_conn = await asyncpg.connect(DATABASE_URL)
    print("Connected to PostgreSQL. Ensuring table schema...")
    await pg_conn.execute(CREATE_TABLE_SQL)

    # Insert / Upsert into PostgreSQL in batch
    insert_sql = """
    INSERT INTO loan_assignments (loan_id, relationship_manager, followup_status, notes, updated_at)
    VALUES ($1, $2, $3, $4, $5)
    ON CONFLICT (loan_id) DO UPDATE 
    SET relationship_manager = EXCLUDED.relationship_manager,
        followup_status = EXCLUDED.followup_status,
        notes = EXCLUDED.notes,
        updated_at = EXCLUDED.updated_at;
    """

    print("Migrating records to PostgreSQL...")
    batch = [
        (r[0], r[1], r[2], r[3] or "", parse_dt(r[4]))
        for r in sqlite_rows
    ]

    await pg_conn.executemany(insert_sql, batch)

    pg_count = await pg_conn.fetchval("SELECT count(*) FROM loan_assignments;")
    print(f"Migration completed successfully! Total rows in PostgreSQL loan_assignments: {pg_count}")
    await pg_conn.close()

if __name__ == "__main__":
    asyncio.run(migrate())
