from contextlib import asynccontextmanager
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.database import init_sqlite_db, connect_to_postgres, close_postgres_connection
from app.views.home import router as home_router
from app.views.api_router import api_router

@asynccontextmanager
async def lifespan(app: FastAPI):
    # Initialize SQLite database schema
    init_sqlite_db()
    # Connect to PostgreSQL connection pool
    await connect_to_postgres()
    yield
    # Close connection pool gracefully on shutdown
    await close_postgres_connection()

app = FastAPI(
    title="Customer Satisfaction Loan Operations API",
    lifespan=lifespan
)

# CORS configuration
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Mount Routers
app.include_router(home_router)
app.include_router(api_router)
