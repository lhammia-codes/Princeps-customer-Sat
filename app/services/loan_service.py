import io
import csv
from datetime import datetime
from typing import Optional, List, Any, Dict, Tuple
from fastapi import HTTPException
import asyncpg

from app.database import get_sqlite_connection, get_pg_pool

MANAGERS = ["Manager A", "Manager B", "Manager C"]

def clean_param(val: Any) -> Optional[str]:
    """Trims whitespace and returns cleaned string or None."""
    if isinstance(val, str) and val.strip():
        return val.strip()
    return None

def clean_int(val: Any, default: int) -> int:
    """Safely parses an integer or returns the fallback default."""
    if isinstance(val, int):
        return val
    try:
        return int(val)
    except (ValueError, TypeError):
        return default

def get_or_assign_relationship_managers(loan_ids: List[str]) -> Dict[str, Dict[str, Any]]:
    """
    Fetches assigned relationship managers for loan IDs, or balances and assigns
    unassigned loans evenly across managers in SQLite.
    """
    if not loan_ids:
        return {}

    conn = get_sqlite_connection()
    cursor = conn.cursor()

    placeholders = ",".join(["?"] * len(loan_ids))
    cursor.execute(
        f"SELECT loan_id, relationship_manager, followup_status, notes FROM loan_assignments WHERE loan_id IN ({placeholders})",
        loan_ids
    )
    existing = {
        row[0]: {
            "relationship_manager": row[1],
            "followup_status": row[2],
            "notes": row[3] or ""
        }
        for row in cursor.fetchall()
    }

    # Count existing assignments across managers to maintain strict equality
    cursor.execute("SELECT relationship_manager, COUNT(*) FROM loan_assignments GROUP BY relationship_manager")
    counts = {m: 0 for m in MANAGERS}
    for rm, cnt in cursor.fetchall():
        if rm in counts:
            counts[rm] = cnt

    new_inserts = []
    for lid in loan_ids:
        if lid not in existing:
            # Assign to manager with the fewest assigned loans
            chosen_rm = min(MANAGERS, key=lambda m: counts[m])
            counts[chosen_rm] += 1
            new_inserts.append((lid, chosen_rm, 'not contacted', ''))
            existing[lid] = {
                "relationship_manager": chosen_rm,
                "followup_status": "not contacted",
                "notes": ""
            }

    if new_inserts:
        cursor.executemany(
            "INSERT OR IGNORE INTO loan_assignments (loan_id, relationship_manager, followup_status, notes) VALUES (?, ?, ?, ?)",
            new_inserts
        )
        conn.commit()

    conn.close()
    return existing

def update_loan_followup(
    loan_id: str,
    status: str,
    notes: Optional[str] = None,
    manager: Optional[str] = None
):
    """Updates or inserts a loan's follow-up status and notes in SQLite."""
    conn = get_sqlite_connection()
    cursor = conn.cursor()

    cursor.execute("SELECT relationship_manager, followup_status, notes FROM loan_assignments WHERE loan_id = ?", (loan_id,))
    row = cursor.fetchone()
    now_str = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

    if row:
        rm = manager or row[0]
        n = notes if notes is not None else row[2]
        cursor.execute("""
            UPDATE loan_assignments 
            SET followup_status = ?, notes = ?, relationship_manager = ?, updated_at = ?
            WHERE loan_id = ?
        """, (status, n, rm, now_str, loan_id))
    else:
        rm = manager or "Manager A"
        cursor.execute("""
            INSERT INTO loan_assignments (loan_id, relationship_manager, followup_status, notes, updated_at)
            VALUES (?, ?, ?, ?, ?)
        """, (loan_id, rm, status, notes or "", now_str))

    conn.commit()
    conn.close()

def build_loan_query(
    start_date: Optional[str] = None,
    end_date: Optional[str] = None,
    status: Optional[str] = None,
    product: Optional[str] = None,
    search: Optional[str] = None
) -> Tuple[str, List[Any]]:
    """Builds parameterized PostgreSQL query for loan disbursements."""
    clauses = []
    params = []
    idx = 1

    clean_start = clean_param(start_date)
    clean_end = clean_param(end_date)
    clean_status = clean_param(status)
    clean_product = clean_param(product)
    clean_search = clean_param(search)

    if clean_start:
        try:
            parsed_start = datetime.strptime(clean_start, "%Y-%m-%d").date()
            clauses.append(f"COALESCE(l.disburse_at, l.created_at) >= ${idx}")
            params.append(parsed_start)
            idx += 1
        except ValueError:
            raise HTTPException(status_code=400, detail="Invalid start_date format. Use YYYY-MM-DD.")

    if clean_end:
        try:
            parsed_end = datetime.strptime(clean_end, "%Y-%m-%d").date()
            clauses.append(f"COALESCE(l.disburse_at, l.created_at) < (${idx}::timestamp + interval '1 day')")
            params.append(parsed_end)
            idx += 1
        except ValueError:
            raise HTTPException(status_code=400, detail="Invalid end_date format. Use YYYY-MM-DD.")

    if clean_status and clean_status.lower() != "all":
        clauses.append(f"LOWER(l.status) = LOWER(${idx})")
        params.append(clean_status)
        idx += 1

    if clean_product and clean_product.lower() != "all":
        clauses.append(f"LOWER(l.loan_product) = LOWER(${idx})")
        params.append(clean_product)
        idx += 1

    if clean_search:
        search_pattern = f"%{clean_search}%"
        clauses.append(f"""(
            c.full_name ILIKE ${idx} OR 
            c.telephone ILIKE ${idx} OR 
            c.email_address ILIKE ${idx} OR 
            c.company_name ILIKE ${idx} OR 
            l.loan_id ILIKE ${idx} OR 
            l.id::text ILIKE ${idx}
        )""")
        params.append(search_pattern)
        idx += 1

    where_sql = ("WHERE " + " AND ".join(clauses)) if clauses else ""

    select_sql = """
        SELECT 
            COALESCE(l.loan_id, l.id::text) AS disbursement_loan_id,
            COALESCE(l.disburse_amount, l.loan_amount, 0)::float AS amount_disbursed,
            l.total_repayment_amount::float AS total_repayment_amount,
            l.instalment_repayment_amount::float AS instalment_repayment_amount,
            l.total_interest::float AS total_interest,
            l.duration AS duration_months,
            l.loan_product,
            l.status AS disbursement_status,
            COALESCE(l.disburse_at, l.created_at)::text AS disbursement_date,
            l.created_at::text AS created_at,
            c.full_name AS customer_name,
            c.telephone AS customer_phone,
            c.email_address AS customer_email,
            c.company_name,
            c.state,
            c.salary_bank_name,
            c.salary_account_number
        FROM caltos_loans l
        JOIN caltos_customers c ON l.customer_id = c.id
    """
    order_sql = "ORDER BY COALESCE(l.disburse_at, l.created_at) DESC"
    query = f"{select_sql} {where_sql} {order_sql}"
    return query, params

async def fetch_and_enrich_disbursements(
    start_date: Optional[str] = None,
    end_date: Optional[str] = None,
    status: Optional[str] = None,
    product: Optional[str] = None,
    search: Optional[str] = None,
    feed: Optional[str] = "all",
    manager: Optional[str] = None,
    limit: int = 500,
    offset: int = 0
) -> List[Dict[str, Any]]:
    """Queries loans from PostgreSQL and enriches them with SQLite assignment & follow-up data."""
    pool = get_pg_pool()
    if not pool:
        raise HTTPException(status_code=500, detail="Database pool not initialized")

    limit_val = clean_int(limit, 500)
    offset_val = clean_int(offset, 0)

    query, params = build_loan_query(
        start_date=start_date,
        end_date=end_date,
        status=status,
        product=product,
        search=search
    )

    idx = len(params) + 1
    query += f" LIMIT ${idx} OFFSET ${idx + 1};"
    params.extend([limit_val, offset_val])

    async with pool.acquire() as connection:
        try:
            rows = await connection.fetch(query, *params)
            raw_items = [dict(row) for row in rows]

            loan_ids = [r['disbursement_loan_id'] for r in raw_items if r.get('disbursement_loan_id')]
            rm_data = get_or_assign_relationship_managers(loan_ids)

            enriched = []
            feed_filter = clean_param(feed) or "all"
            manager_filter = clean_param(manager)

            for item in raw_items:
                lid = item.get('disbursement_loan_id')
                rm_info = rm_data.get(lid, {
                    "relationship_manager": "Manager A",
                    "followup_status": "not contacted",
                    "notes": ""
                })
                item['relationship_manager'] = rm_info['relationship_manager']
                item['followup_status'] = rm_info['followup_status']
                item['followup_notes'] = rm_info['notes']

                # Feed filter:
                # - "pending": only show uncompleted loans (not contacted or sms sent)
                # - "completed": only show contacted loans
                # - "all": show everything
                if feed_filter == "pending" and item['followup_status'] == "contacted":
                    continue
                if feed_filter == "completed" and item['followup_status'] != "contacted":
                    continue

                # Manager filter
                if manager_filter and manager_filter.lower() != "all":
                    if item['relationship_manager'].lower() != manager_filter.lower():
                        continue

                enriched.append(item)

            return enriched
        except Exception as e:
            print(f"DATABASE QUERY ERROR: {str(e)}")
            raise HTTPException(status_code=500, detail=f"Database query failed: {str(e)}")

async def fetch_filter_options() -> Dict[str, List[str]]:
    """Retrieves unique products and statuses from the database."""
    pool = get_pg_pool()
    if not pool:
        raise HTTPException(status_code=500, detail="Database pool not initialized")

    query_products = "SELECT DISTINCT loan_product FROM caltos_loans WHERE loan_product IS NOT NULL ORDER BY loan_product;"
    query_statuses = "SELECT DISTINCT status FROM caltos_loans WHERE status IS NOT NULL ORDER BY status;"

    async with pool.acquire() as connection:
        try:
            product_rows = await connection.fetch(query_products)
            status_rows = await connection.fetch(query_statuses)
            return {
                "products": [r['loan_product'] for r in product_rows if r['loan_product']],
                "statuses": [r['status'] for r in status_rows if r['status']],
                "managers": MANAGERS,
                "followup_statuses": ["not contacted", "contacted", "not reachable but sms sent"]
            }
        except Exception as e:
            raise HTTPException(status_code=500, detail=f"Failed to fetch filters: {str(e)}")

async def generate_loans_csv(
    start_date: Optional[str] = None,
    end_date: Optional[str] = None,
    status: Optional[str] = None,
    product: Optional[str] = None,
    search: Optional[str] = None,
    feed: Optional[str] = "all",
    manager: Optional[str] = None,
    limit: int = 5000
) -> Tuple[str, str]:
    """Generates a CSV string of loans matching the requested filters along with a generated filename."""
    pool = get_pg_pool()
    if not pool:
        raise HTTPException(status_code=500, detail="Database pool not initialized")

    limit_val = clean_int(limit, 5000)
    query, params = build_loan_query(
        start_date=start_date,
        end_date=end_date,
        status=status,
        product=product,
        search=search
    )
    idx = len(params) + 1
    query += f" LIMIT ${idx};"
    params.append(limit_val)

    async with pool.acquire() as connection:
        rows = await connection.fetch(query, *params)
        raw_items = [dict(row) for row in rows]

    loan_ids = [r['disbursement_loan_id'] for r in raw_items if r.get('disbursement_loan_id')]
    rm_data = get_or_assign_relationship_managers(loan_ids)

    output = io.StringIO()
    writer = csv.writer(output)

    # Header row
    writer.writerow([
        "Loan ID",
        "Customer Name",
        "Phone Number",
        "Email Address",
        "Company Name",
        "State",
        "Loan Product",
        "Amount Disbursed (NGN)",
        "Total Repayment (NGN)",
        "Monthly Instalment (NGN)",
        "Total Interest (NGN)",
        "Tenor (Months)",
        "Status",
        "Disbursement Date",
        "Relationship Manager",
        "Follow-up Status",
        "Salary Bank",
        "Salary Account"
    ])

    feed_filter = clean_param(feed) or "all"
    manager_filter = clean_param(manager)

    for r in raw_items:
        lid = r.get('disbursement_loan_id')
        rm_info = rm_data.get(lid, {"relationship_manager": "Manager A", "followup_status": "not contacted"})
        rm_val = rm_info['relationship_manager']
        f_status = rm_info['followup_status']

        if feed_filter == "pending" and f_status == "contacted":
            continue
        if feed_filter == "completed" and f_status != "contacted":
            continue
        if manager_filter and manager_filter.lower() != "all":
            if rm_val.lower() != manager_filter.lower():
                continue

        writer.writerow([
            r['disbursement_loan_id'] or "",
            r['customer_name'] or "",
            r['customer_phone'] or "",
            r['customer_email'] or "",
            r['company_name'] or "",
            r['state'] or "",
            r['loan_product'] or "",
            r['amount_disbursed'] or 0.0,
            r['total_repayment_amount'] or 0.0,
            r['instalment_repayment_amount'] or 0.0,
            r['total_interest'] or 0.0,
            r['duration_months'] or "",
            r['disbursement_status'] or "",
            r['disbursement_date'] or "",
            rm_val,
            f_status,
            r['salary_bank_name'] or "",
            r['salary_account_number'] or ""
        ])

    csv_data = output.getvalue()
    filename = f"loan_disbursements_{datetime.now().strftime('%Y%m%d_%H%M%S')}.csv"
    return csv_data, filename
