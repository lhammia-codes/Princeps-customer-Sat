from typing import Optional
from fastapi import APIRouter, Query

from app.schemas.stats import DashboardStats, ROStatsResponse
from app.services.stats_service import fetch_dashboard_stats, fetch_ro_stats

router = APIRouter()

@router.get("/stats", response_model=DashboardStats)
async def get_dashboard_stats():
    """Returns today, monthly, and overall disbursement volume metrics."""
    return await fetch_dashboard_stats()

@router.get("/ro/stats", response_model=ROStatsResponse)
async def get_ro_stats(
    start_date: Optional[str] = Query(None, description="Start date YYYY-MM-DD (defaults to today)"),
    end_date: Optional[str] = Query(None, description="End date YYYY-MM-DD (defaults to today)")
):
    """Returns relationship officer performance and completion metrics."""
    return await fetch_ro_stats(start_date=start_date, end_date=end_date)
