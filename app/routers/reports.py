from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.orm import Session

from app.core.permissions import assert_can_access_employee, is_super_admin
from app.crud.auth import require_admin
from app.database.database import get_db
from app.schemas.reports import AttendanceMonthlySummary
from app.services.reports import (
    attendance_summary_for_company, attendance_summary_for_employee,
)
from app.utils.api_response import ApiResponse

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
    if is_super_admin(user):
        if company_id is None:
            raise HTTPException(
                400,
                "company_id is required for super_admin to scope the report"
            )
    else:
        company_id = user.company_id

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
