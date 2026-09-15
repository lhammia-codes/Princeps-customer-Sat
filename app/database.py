import sqlite3
from typing import Optional
import asyncpg
from app.config import DATABASE_URL, SQLITE_DB_PATH

db_pool: Optional[asyncpg.Pool] = None

def get_sqlite_connection() -> sqlite3.Connection:
    """Returns a SQLite connection to the local operations database."""
    return sqlite3.connect(SQLITE_DB_PATH)

def init_sqlite_db():
    """Initializes the SQLite database tables and indexes if they do not exist."""
    conn = get_sqlite_connection()
    cursor = conn.cursor()
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS loan_assignments (
            loan_id TEXT PRIMARY KEY,
            relationship_manager TEXT NOT NULL,
            followup_status TEXT NOT NULL DEFAULT 'not contacted',
            notes TEXT,
            updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        );
    """)
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_loan_assignments_rm ON loan_assignments(relationship_manager);")
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_loan_assignments_status ON loan_assignments(followup_status);")
    conn.commit()
    conn.close()

async def connect_to_postgres() -> asyncpg.Pool:
    """Initializes the asyncpg connection pool to PostgreSQL."""
    global db_pool
    db_pool = await asyncpg.create_pool(
        DATABASE_URL,
        min_size=2,
        max_size=10,
        command_timeout=60,
        max_inactive_connection_lifetime=300
    )
    return db_pool

async def close_postgres_connection():
    """Closes the asyncpg connection pool if active."""
    global db_pool
    if db_pool:
        await db_pool.close()
        db_pool = None

def get_pg_pool() -> Optional[asyncpg.Pool]:
    """Returns the current asyncpg connection pool."""
    return db_pool
