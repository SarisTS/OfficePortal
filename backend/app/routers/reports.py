from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.orm import Session

from app.core.permissions import assert_can_access_employee, is_super_admin
from app.crud.auth import require_admin
from app.database.database import get_db
from app.schemas.reports import (
    AttendanceMonthlySummary, LeaveUsageRow, PayrollMonthlyTotal,
)
from app.services.reports import (
    attendance_summary_for_company, attendance_summary_for_employee,
    leave_usage_for_company, payroll_totals_for_company,
)
from app.utils.api_response import ApiResponse


def _resolve_company_scope(user, company_id: int | None) -> int:
    """Centralized scope rule for company-level reports.

    super_admin   must pass company_id (avoids implicit cross-tenant
                  reports — keeps response sizes bounded and prevents
                  accidental leaks)
    office_admin  company_id is ignored, scoped to their own
    """
    if is_super_admin(user):
        if company_id is None:
            raise HTTPException(
                400,
                "company_id is required for super_admin to scope the report"
            )
        return company_id
    return user.company_id

router = APIRouter(tags=["Reports"])


@router.get(
    "/attendance/monthly",
    response_model=ApiResponse[list[AttendanceMonthlySummary]],
)
def attendance_monthly(
    year: int = Query(..., ge=2000, le=2100),
    month: int = Query(..., ge=1, le=12),
    company_id: int | None = Query(None),
    db: Session = Depends(get_db),
    user=Depends(require_admin),
):
    """Per-employee attendance summary for one (year, month).

    Scope:
      super_admin    must pass company_id (no cross-tenant implicit
                     reports — keeps the table size bounded)
      office_admin   company_id query param is ignored; the report
                     covers their own company
    """
    company_id = _resolve_company_scope(user, company_id)
    items = attendance_summary_for_company(db, company_id, year, month)
    return {
        "status": status.HTTP_200_OK,
        "message": f"Monthly attendance summary for {year}-{month:02d}",
        "data": items,
    }


@router.get(
    "/attendance/employee/{employee_id}/monthly",
    response_model=ApiResponse[AttendanceMonthlySummary],
)
def attendance_employee_monthly(
    employee_id: int,
    year: int = Query(..., ge=2000, le=2100),
    month: int = Query(..., ge=1, le=12),
    db: Session = Depends(get_db),
    user=Depends(require_admin),
):
    """Single-employee monthly summary. tenant-checked via
    assert_can_access_employee. Returns zeros (not 404) when the
    employee has no rows in the period."""
    target = assert_can_access_employee(db, employee_id, user)
    summary = attendance_summary_for_employee(db, target.id, year, month)
    return {
        "status": status.HTTP_200_OK,
        "message": f"Monthly attendance for employee {employee_id}",
        "data": summary,
    }


@router.get(
    "/leave/usage",
    response_model=ApiResponse[list[LeaveUsageRow]],
)
def leave_usage(
    year: int = Query(..., ge=2000, le=2100),
    company_id: int | None = Query(None),
    db: Session = Depends(get_db),
    user=Depends(require_admin),
):
    """Per-leave-type usage rollup for one (company, year).

    Combines balance aggregation (SUM allocated/used across all
    employees) with a pending-leaves count (leaves whose start_date
    falls in the year and are still in `pending`).
    """
    company_id = _resolve_company_scope(user, company_id)
    rows = leave_usage_for_company(db, company_id, year)
    return {
        "status": status.HTTP_200_OK,
        "message": f"Leave usage for {year}",
        "data": rows,
    }


@router.get(
    "/payroll/monthly",
    response_model=ApiResponse[PayrollMonthlyTotal],
)
def payroll_monthly(
    year: int = Query(..., ge=2000, le=2100),
    month: int = Query(..., ge=1, le=12),
    company_id: int | None = Query(None),
    db: Session = Depends(get_db),
    user=Depends(require_admin),
):
    """Company-wide payroll totals for one (year, month).

    payslip_count + total_gross + total_deductions + total_net +
    average_net. Empty period (no payslips) returns zeros, not 404.
    """
    company_id = _resolve_company_scope(user, company_id)
    totals = payroll_totals_for_company(db, company_id, year, month)
    return {
        "status": status.HTTP_200_OK,
        "message": f"Payroll totals for {year}-{month:02d}",
        "data": totals,
    }
