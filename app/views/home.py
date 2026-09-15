import os
from fastapi import APIRouter
from fastapi.responses import HTMLResponse
from app.config import INDEX_HTML_PATH

router = APIRouter()

@router.get("/", response_class=HTMLResponse, include_in_schema=False)
async def serve_dashboard():
    """Serves the Customer Satisfaction Operations dashboard frontend."""
    if os.path.exists(INDEX_HTML_PATH):
        with open(INDEX_HTML_PATH, "r", encoding="utf-8") as f:
            return f.read()
    return "<h3>index.html not found in project directory.</h3>"
