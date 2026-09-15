from typing import Optional, List
from pydantic import BaseModel

class LoanDisbursementItem(BaseModel):
    disbursement_loan_id: Optional[str] = None
    amount_disbursed: Optional[float] = None
    total_repayment_amount: Optional[float] = None
    instalment_repayment_amount: Optional[float] = None
    total_interest: Optional[float] = None
    duration_months: Optional[int] = None
    loan_product: Optional[str] = None
    disbursement_status: Optional[str] = None
    disbursement_date: Optional[str] = None
    created_at: Optional[str] = None
    customer_name: Optional[str] = None
    customer_phone: Optional[str] = None
    customer_email: Optional[str] = None
    company_name: Optional[str] = None
    state: Optional[str] = None
    salary_bank_name: Optional[str] = None
    salary_account_number: Optional[str] = None
    relationship_manager: Optional[str] = "Manager A"
    followup_status: Optional[str] = "not contacted"
    followup_notes: Optional[str] = ""

class FollowupUpdateRequest(BaseModel):
    followup_status: str
    notes: Optional[str] = None
    relationship_manager: Optional[str] = None

class FilterOptionsResponse(BaseModel):
    products: List[str]
    statuses: List[str]
    managers: List[str]
    followup_statuses: List[str]
