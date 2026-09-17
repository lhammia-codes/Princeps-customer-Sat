from typing import Optional, List
from fastapi import APIRouter, HTTPException, Query, Response

from app.schemas.loan import (
    LoanDisbursementItem,
    FollowupUpdateRequest,
    FilterOptionsResponse
)
from app.services.loan_service import (
    fetch_and_enrich_disbursements,
    update_loan_followup,
    fetch_filter_options,
    generate_loans_csv
)

router = APIRouter()

@router.get("/disbursements", response_model=List[LoanDisbursementItem])
async def get_loan_disbursements(
    start_date: Optional[str] = Query(None, description="Start date YYYY-MM-DD"),
    end_date: Optional[str] = Query(None, description="End date YYYY-MM-DD"),
    status: Optional[str] = Query(None, description="Filter by status (e.g. DISBURSED, all)"),
    product: Optional[str] = Query(None, description="Filter by loan product"),
    search: Optional[str] = Query(None, description="Search customer name, phone, loan ID, company"),
    feed: Optional[str] = Query("all", description="Filter by feed: pending, completed, all"),
    manager: Optional[str] = Query(None, description="Filter by relationship manager: Manager A, Manager B, Manager C"),
    limit: int = Query(500, ge=1, le=2000),
    offset: int = Query(0, ge=0)
):
    """Retrieves loan disbursements from PostgreSQL enriched with relationship manager assignments."""
    return await fetch_and_enrich_disbursements(
        start_date=start_date,
        end_date=end_date,
        status=status,
        product=product,
        search=search,
        feed=feed,
        manager=manager,
        limit=limit,
        offset=offset
    )

@router.post("/{loan_id}/followup")
async def update_loan_status(loan_id: str, req: FollowupUpdateRequest):
    """Updates follow-up status, notes, and assigned manager for a specific loan."""
    valid_statuses = ["contacted", "not contacted", "not reachable but sms sent"]
    if req.followup_status not in valid_statuses:
        raise HTTPException(
            status_code=400,
            detail=f"Invalid followup_status. Must be one of: {valid_statuses}"
        )

    await update_loan_followup(
        loan_id=loan_id,
        status=req.followup_status,
        notes=req.notes,
        manager=req.relationship_manager
    )
    return {
        "status": "success",
        "loan_id": loan_id,
        "followup_status": req.followup_status,
        "notes": req.notes,
        "relationship_manager": req.relationship_manager
    }

@router.get("/filters", response_model=FilterOptionsResponse)
async def get_filter_options():
    """Returns available filter options for loan products, statuses, and relationship managers."""
    return await fetch_filter_options()

@router.get("/export")
async def export_loans_csv(
    start_date: Optional[str] = Query(None),
    end_date: Optional[str] = Query(None),
    status: Optional[str] = Query(None),
    product: Optional[str] = Query(None),
    search: Optional[str] = Query(None),
    feed: Optional[str] = Query("all"),
    manager: Optional[str] = Query(None),
    limit: int = Query(5000, le=10000)
):
    """Exports filtered loan disbursements as a downloadable CSV file."""
    csv_data, filename = await generate_loans_csv(
        start_date=start_date,
        end_date=end_date,
        status=status,
        product=product,
        search=search,
        feed=feed,
        manager=manager,
        limit=limit
    )

    return Response(
        content=csv_data,
        media_type="text/csv",
        headers={"Content-Disposition": f"attachment; filename={filename}"}
    )
