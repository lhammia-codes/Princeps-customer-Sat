from typing import Optional, Dict
from pydantic import BaseModel

class DashboardStats(BaseModel):
    today_disbursements_count: int
    today_disbursed_amount: float
    month_disbursements_count: int
    month_disbursed_amount: float
    total_disbursements_count: int
    total_disbursed_amount: float
    latest_disbursement_time: Optional[str] = None
    pending_feed_count: int = 0
    completed_feed_count: int = 0

class ManagerPerformance(BaseModel):
    total: int
    completed: int
    not_contacted: int
    sms_sent: int
    pending: int
    completion_rate: float

class ROStatsResponse(BaseModel):
    total_disbursed_feed_count: int
    total_completed_count: int
    total_tracked_loans: int
    team_completion_rate: float
    managers: Dict[str, ManagerPerformance]
