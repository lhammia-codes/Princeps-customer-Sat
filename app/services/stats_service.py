from datetime import datetime
from typing import Optional, List, Dict, Any
from fastapi import HTTPException

from app.database import get_pg_pool
from app.schemas.stats import DashboardStats
from app.services.loan_service import (
    clean_param,
    get_or_assign_relationship_managers,
    MANAGERS
)

async def get_ro_dashboard_statistics(loan_ids: Optional[List[str]] = None) -> Dict[str, Any]:
    """Calculates relationship officer follow-up stats from PostgreSQL."""
    pool = await get_pg_pool()

    if loan_ids is not None and not loan_ids:
        return {
            "total_disbursed_feed_count": 0,
            "total_completed_count": 0,
            "total_tracked_loans": 0,
            "total_spillover_count": 0,
            "team_completion_rate": 0.0,
            "team_spillover_rate": 0.0,
            "managers": {
                m: {
                    "total": 0,
                    "completed": 0,
                    "not_contacted": 0,
                    "sms_sent": 0,
                    "pending": 0,
                    "spillover": 0,
                    "completion_rate": 0.0,
                    "spillover_rate": 0.0
                }
                for m in MANAGERS
            }
        }

    async with pool.acquire() as conn:
        if loan_ids is not None:
            rows = await conn.fetch("""
                SELECT 
                    relationship_manager,
                    COUNT(*) as total,
                    SUM(CASE WHEN followup_status = 'contacted' THEN 1 ELSE 0 END) as completed,
                    SUM(CASE WHEN followup_status = 'not contacted' THEN 1 ELSE 0 END) as not_contacted,
                    SUM(CASE WHEN followup_status = 'not reachable but sms sent' THEN 1 ELSE 0 END) as sms_sent
                FROM loan_assignments
                WHERE loan_id = ANY($1::text[])
                GROUP BY relationship_manager;
            """, loan_ids)
        else:
            rows = await conn.fetch("""
                SELECT 
                    relationship_manager,
                    COUNT(*) as total,
                    SUM(CASE WHEN followup_status = 'contacted' THEN 1 ELSE 0 END) as completed,
                    SUM(CASE WHEN followup_status = 'not contacted' THEN 1 ELSE 0 END) as not_contacted,
                    SUM(CASE WHEN followup_status = 'not reachable but sms sent' THEN 1 ELSE 0 END) as sms_sent
                FROM loan_assignments
                GROUP BY relationship_manager;
            """)

    manager_data = {
        m: {
            "total": 0,
            "completed": 0,
            "not_contacted": 0,
            "sms_sent": 0,
            "pending": 0,
            "spillover": 0,
            "completion_rate": 0.0,
            "spillover_rate": 0.0
        }
        for m in MANAGERS
    }

    total_loans = 0
    total_completed = 0
    total_pending = 0

    for r in rows:
        rm = r['relationship_manager']
        tot = r['total'] or 0
        comp = r['completed'] or 0
        not_cont = r['not_contacted'] or 0
        sms = r['sms_sent'] or 0

        if rm in manager_data:
            pending = tot - comp
            spillover = pending
            rate = round((comp / tot * 100), 1) if tot > 0 else 0.0
            spillover_rate = round((pending / tot * 100), 1) if tot > 0 else 0.0
            manager_data[rm] = {
                "total": tot,
                "completed": comp,
                "not_contacted": not_cont,
                "sms_sent": sms,
                "pending": pending,
                "spillover": spillover,
                "completion_rate": rate,
                "spillover_rate": spillover_rate
            }
            total_loans += tot
            total_completed += comp
            total_pending += pending

    team_rate = round((total_completed / total_loans * 100), 1) if total_loans > 0 else 0.0
    team_spillover_rate = round((total_pending / total_loans * 100), 1) if total_loans > 0 else 0.0

    return {
        "total_disbursed_feed_count": total_pending,
        "total_completed_count": total_completed,
        "total_tracked_loans": total_loans,
        "total_spillover_count": total_pending,
        "team_completion_rate": team_rate,
        "team_spillover_rate": team_spillover_rate,
        "managers": manager_data
    }

async def fetch_ro_stats(
    start_date: Optional[str] = None,
    end_date: Optional[str] = None
) -> Dict[str, Any]:
    """Retrieves RO stats for loans disbursed within the specified timeframe (defaulting to today)."""
    pool = await get_pg_pool()

    clean_start = clean_param(start_date)
    clean_end = clean_param(end_date)

    clauses = ["status = 'DISBURSED'"]
    params = []
    idx = 1

    is_all_time = (clean_start and clean_start.lower() == "all") or (clean_end and clean_end.lower() == "all")

    if is_all_time:
        # No date filters applied for all-time view
        pass
    else:
        if clean_start:
            try:
                parsed_start = datetime.strptime(clean_start, "%Y-%m-%d").date()
                clauses.append(f"COALESCE(disburse_at, created_at) >= ${idx}")
                params.append(parsed_start)
                idx += 1
            except ValueError:
                raise HTTPException(status_code=400, detail="Invalid start_date format. Use YYYY-MM-DD.")
        elif not clean_end:
            clauses.append("COALESCE(disburse_at, created_at) >= CURRENT_DATE")

        if clean_end:
            try:
                parsed_end = datetime.strptime(clean_end, "%Y-%m-%d").date()
                clauses.append(f"COALESCE(disburse_at, created_at) < (${idx}::timestamp + interval '1 day')")
                params.append(parsed_end)
                idx += 1
            except ValueError:
                raise HTTPException(status_code=400, detail="Invalid end_date format. Use YYYY-MM-DD.")
        elif not clean_start:
            clauses.append("COALESCE(disburse_at, created_at) < (CURRENT_DATE + interval '1 day')")

    where_sql = " AND ".join(clauses)
    ids_query = f"""
        SELECT COALESCE(loan_id, id::text) AS loan_id
        FROM caltos_loans
        WHERE {where_sql};
    """

    async with pool.acquire() as connection:
        try:
            id_rows = await connection.fetch(ids_query, *params)
            loan_ids = [r['loan_id'] for r in id_rows if r['loan_id']]

            await get_or_assign_relationship_managers(loan_ids)
            stats = await get_ro_dashboard_statistics(loan_ids=loan_ids)
            stats["period"] = {
                "start_date": None if is_all_time else clean_start,
                "end_date": None if is_all_time else clean_end
            }
            return stats
        except Exception as e:
            print(f"RO STATS QUERY ERROR: {str(e)}")
            raise HTTPException(status_code=500, detail=f"RO stats query failed: {str(e)}")

async def fetch_dashboard_stats() -> DashboardStats:
    """Retrieves high-level volume metrics and today's pending/completed feed counts."""
    pool = await get_pg_pool()

    query = """
        SELECT 
            COUNT(CASE WHEN status = 'DISBURSED' AND (disburse_at >= CURRENT_DATE OR (disburse_at IS NULL AND created_at >= CURRENT_DATE)) THEN 1 END) AS today_count,
            COALESCE(SUM(CASE WHEN status = 'DISBURSED' AND (disburse_at >= CURRENT_DATE OR (disburse_at IS NULL AND created_at >= CURRENT_DATE)) THEN COALESCE(disburse_amount, loan_amount, 0) END), 0)::float AS today_amount,
            
            COUNT(CASE WHEN status = 'DISBURSED' AND (disburse_at >= date_trunc('month', CURRENT_DATE) OR (disburse_at IS NULL AND created_at >= date_trunc('month', CURRENT_DATE))) THEN 1 END) AS month_count,
            COALESCE(SUM(CASE WHEN status = 'DISBURSED' AND (disburse_at >= date_trunc('month', CURRENT_DATE) OR (disburse_at IS NULL AND created_at >= date_trunc('month', CURRENT_DATE))) THEN COALESCE(disburse_amount, loan_amount, 0) END), 0)::float AS month_amount,

            COUNT(CASE WHEN status = 'DISBURSED' THEN 1 END) AS total_count,
            COALESCE(SUM(CASE WHEN status = 'DISBURSED' THEN COALESCE(disburse_amount, loan_amount, 0) END), 0)::float AS total_amount,

            MAX(COALESCE(disburse_at, created_at))::text AS latest_disbursement_time
        FROM caltos_loans;
    """
    today_ids_query = """
        SELECT COALESCE(loan_id, id::text) AS loan_id
        FROM caltos_loans
        WHERE status = 'DISBURSED'
          AND (disburse_at >= CURRENT_DATE OR (disburse_at IS NULL AND created_at >= CURRENT_DATE));
    """

    async with pool.acquire() as connection:
        try:
            row = await connection.fetchrow(query)
            today_id_rows = await connection.fetch(today_ids_query)
            today_loan_ids = [r['loan_id'] for r in today_id_rows if r['loan_id']]

            await get_or_assign_relationship_managers(today_loan_ids)
            ro_stats = await get_ro_dashboard_statistics(loan_ids=today_loan_ids)

            return DashboardStats(
                today_disbursements_count=row['today_count'] or 0,
                today_disbursed_amount=row['today_amount'] or 0.0,
                month_disbursements_count=row['month_count'] or 0,
                month_disbursed_amount=row['month_amount'] or 0.0,
                total_disbursements_count=row['total_count'] or 0,
                total_disbursed_amount=row['total_amount'] or 0.0,
                latest_disbursement_time=row['latest_disbursement_time'],
                pending_feed_count=ro_stats['total_disbursed_feed_count'],
                completed_feed_count=ro_stats['total_completed_count']
            )
        except Exception as e:
            print(f"STATS QUERY ERROR: {str(e)}")
            raise HTTPException(status_code=500, detail=f"Stats query failed: {str(e)}")
