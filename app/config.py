import os
from pathlib import Path
from dotenv import load_dotenv

# Base directory: Princeps customer Sat/
BASE_DIR = Path(__file__).resolve().parent.parent

# Load .env file from project root
load_dotenv(dotenv_path=BASE_DIR / ".env")

DATABASE_URL = os.getenv("DATABASE_URL") or "postgresql://data:Caltos%402222@194.163.180.41:5432/data_reporting_warehouse"
SQLITE_DB_PATH = os.getenv("SQLITE_DB_PATH", str(BASE_DIR / "cs_operations.db"))
INDEX_HTML_PATH = os.getenv("INDEX_HTML_PATH", str(BASE_DIR / "index.html"))
