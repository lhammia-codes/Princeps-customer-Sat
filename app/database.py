from typing import Optional
import asyncpg
from app.config import DATABASE_URL

db_pool: Optional[asyncpg.Pool] = None

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

async def init_postgres_schema(pool: asyncpg.Pool):
    """Ensures necessary operational tables and indexes exist in PostgreSQL."""
    async with pool.acquire() as conn:
        await conn.execute(CREATE_TABLE_SQL)

async def connect_to_postgres() -> asyncpg.Pool:
    """Initializes the asyncpg connection pool and verifies table schemas."""
    global db_pool
    if db_pool is None or db_pool._closed:
        db_pool = await asyncpg.create_pool(
            DATABASE_URL,
            min_size=1,
            max_size=5,
            command_timeout=60,
            max_inactive_connection_lifetime=300
        )
        await init_postgres_schema(db_pool)
    return db_pool

async def close_postgres_connection():
    """Closes the asyncpg connection pool gracefully."""
    global db_pool
    if db_pool and not db_pool._closed:
        await db_pool.close()
        db_pool = None

async def get_pg_pool() -> asyncpg.Pool:
    """Returns the active asyncpg connection pool, initializing it if needed (serverless friendly)."""
    global db_pool
    if db_pool is None or db_pool._closed:
        return await connect_to_postgres()
    return db_pool
