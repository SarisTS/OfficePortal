"""Endpoints scoped to the authenticated user (self-service).

The /me/* namespace is for things the user does to their OWN account.
Anything admin-mediated belongs in the matching resource router instead
(/employees/{id}, etc.). Today: profile read + edit, holidays + weekly
offs, current salary structure, leave list, shift current/history,
latest payslip.
"""
from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.orm import Session

from app.crud import assignment as shift_crud
from app.crud import holiday as holiday_crud
from app.crud.auth import get_current_user
from app.crud.employee import update_own_profile
from app.crud.salary_structure import get_current_structure
from app.database.database import get_db
from app.models.employee import Employee
from app.models.holiday import CompanyHoliday, CompanyWeeklyOff
from app.models.leave import Leave, LeaveStatus, LeaveType
from app.models.payslip import Payslip
from app.schemas.assignment import ShiftAssignmentResponse
from app.schemas.employee import EmployeeResponse, ProfileUpdate
from app.schemas.holiday import (
    CompanyHolidayResponse, CompanyWeeklyOffResponse,
)
from app.schemas.leave import LeaveResponse
from app.schemas.payslip import PayslipResponse, SalaryStructureResponse
from app.utils.api_response import ApiResponse, PaginatedResponse

router = APIRouter(tags=["Me"])


@router.get("/profile", response_model=ApiResponse[EmployeeResponse])
def get_my_profile(user: Employee = Depends(get_current_user)):
    """Read the authenticated user's profile.

    Same sanitization as /auth/me — password_hash and google_id are not
    in EmployeeResponse so they cannot leak through this projection.
    """
    return {
        "status": status.HTTP_200_OK,
        "message": "Profile fetched",
        "data": EmployeeResponse.model_validate(user),
    }


@router.put("/profile", response_model=ApiResponse[EmployeeResponse])
def update_my_profile(
    data: ProfileUpdate,
    db: Session = Depends(get_db),
    user: Employee = Depends(get_current_user),
):
    """Self-service edit. Whitelist + uniqueness pre-check lives in
    crud.employee.update_own_profile."""
    updated = update_own_profile(db, user, data)
    return {
        "status": status.HTTP_200_OK,
        "message": "Profile updated",
        "data": EmployeeResponse.model_validate(updated),
    }


@router.get(
    "/holidays",
    response_model=ApiResponse[list[CompanyHolidayResponse]],
)
def list_my_holidays(
    year: int | None = Query(None, ge=2000, le=2100),
    month: int | None = Query(None, ge=1, le=12),
    db: Session = Depends(get_db),
    user: Employee = Depends(get_current_user),
):
    """Self-service holiday list. Scoped to the caller's company.

    Employees not associated with a company (super_admin) get an empty
    list — they don't have a calendar to consult."""
    if user.company_id is None:
        return {
            "status": status.HTTP_200_OK,
            "message": "No company on file; no holidays to list",
            "data": [],
        }

    query = db.query(CompanyHoliday).filter(
        CompanyHoliday.company_id == user.company_id,
        CompanyHoliday.deleted_at.is_(None),
    )
    if year is not None:
        from datetime import date as _date
        query = query.filter(
            CompanyHoliday.date >= _date(year, 1, 1),
            CompanyHoliday.date <= _date(year, 12, 31),
        )
    if month is not None:
        if year is None:
            raise HTTPException(400, "month filter requires year")
        from calendar import monthrange
        from datetime import date as _date
        _, last = monthrange(year, month)
        query = query.filter(
            CompanyHoliday.date >= _date(year, month, 1),
            CompanyHoliday.date <= _date(year, month, last),
        )

    items = query.order_by(CompanyHoliday.date).all()
    return {
        "status": status.HTTP_200_OK,
        "message": "Holidays fetched",
        "data": items,
    }


@router.get(
    "/weekly-offs",
    response_model=ApiResponse[list[CompanyWeeklyOffResponse]],
)
def list_my_weekly_offs(
    db: Session = Depends(get_db),
    user: Employee = Depends(get_current_user),
):
    """Self-service list of recurring weekly-off days for the caller's
    company. Empty list when the caller has no company on file."""
    if user.company_id is None:
        return {
            "status": status.HTTP_200_OK,
            "message": "No company on file; no weekly offs to list",
            "data": [],
        }
    items = (
        db.query(CompanyWeeklyOff)
        .filter(
            CompanyWeeklyOff.company_id == user.company_id,
            CompanyWeeklyOff.deleted_at.is_(None),
        )
        .order_by(CompanyWeeklyOff.day_of_week)
        .all()
    )
    return {
        "status": status.HTTP_200_OK,
        "message": "Weekly offs fetched",
        "data": items,
    }


@router.get("/salary", response_model=ApiResponse[SalaryStructureResponse])
def get_my_current_salary(
    db: Session = Depends(get_db),
    user: Employee = Depends(get_current_user),
):
    """Return the SalaryStructure active for the caller today.

    404 if the caller has no structure on file yet (admin hasn't created
    one). Past structures aren't surfaced here — for history, admins
    can read via GET /salary-structures/employee/{id}.
    """
    structure = get_current_structure(db, user.id)
    if structure is None:
        raise HTTPException(404, "No active salary structure on file")
    return {
        "status": status.HTTP_200_OK,
        "message": "Current salary structure",
        "data": SalaryStructureResponse.model_validate(structure),
    }


# ---------------------------------------------------------------------------
# Self-service mobile endpoints (added in Phase 1 stabilization).
#
# These are thin convenience wrappers around existing CRUD: the Flutter
# app needs URLs under /me/* rather than passing its own employee_id
# into admin-flavored endpoints like /leave/employee/{id}.
# ---------------------------------------------------------------------------


@router.get("/leaves", response_model=ApiResponse[list[LeaveResponse]])
def list_my_leaves(
    year: int | None = Query(None, ge=2000, le=2100),
    month: int | None = Query(None, ge=1, le=12),
    leave_type: LeaveType | None = Query(None),
    leave_status: LeaveStatus | None = Query(None, alias="status"),
    db: Session = Depends(get_db),
    user: Employee = Depends(get_current_user),
):
    """The caller's own leaves. Filterable by year, month, leave_type
    and status. `month` requires `year` to be set."""
    if month is not None and year is None:
        raise HTTPException(400, "month filter requires year")

    query = db.query(Leave).filter(
        Leave.employee_id == user.id,
        Leave.deleted_at.is_(None),
    )

    if year is not None:
        from datetime import date as _date
        if month is None:
            query = query.filter(
                Leave.start_date <= _date(year, 12, 31),
                Leave.end_date >= _date(year, 1, 1),
            )
        else:
            from calendar import monthrange
            _, last = monthrange(year, month)
            query = query.filter(
                Leave.start_date <= _date(year, month, last),
                Leave.end_date >= _date(year, month, 1),
            )

    if leave_type is not None:
        query = query.filter(Leave.leave_type == leave_type)
    if leave_status is not None:
        query = query.filter(Leave.status == leave_status)

    items = query.order_by(Leave.start_date.desc()).all()
    return {
        "status": status.HTTP_200_OK,
        "message": "Leaves fetched",
        "data": items,
    }


@router.get(
    "/shifts/current", response_model=ApiResponse[ShiftAssignmentResponse]
)
def get_my_current_shift(
    db: Session = Depends(get_db),
    user: Employee = Depends(get_current_user),
):
    """The caller's active shift assignment, or 404 if none."""
    result = shift_crud.get_current_shift(db, user.id, user)
    if result is None:
        raise HTTPException(404, "No active shift assignment")
    return {
        "status": status.HTTP_200_OK,
        "message": "Current shift fetched",
        "data": result,
    }


@router.get(
    "/shifts/history",
    response_model=ApiResponse[PaginatedResponse[ShiftAssignmentResponse]],
)
def get_my_shift_history(
    skip: int = Query(0, ge=0),
    limit: int = Query(10, ge=1, le=100),
    db: Session = Depends(get_db),
    user: Employee = Depends(get_current_user),
):
    """Paginated history of the caller's shift assignments."""
    total, items = shift_crud.get_employee_shift_history(
        db, user.id, user, skip=skip, limit=limit
    )
    return {
        "status": status.HTTP_200_OK,
        "message": "Shift history fetched",
        "data": {
            "skip": skip,
            "limit": limit,
            "total": total,
            "items": items,
        },
    }


@router.get(
    "/payslips/latest", response_model=ApiResponse[PayslipResponse]
)
def get_my_latest_payslip(
    db: Session = Depends(get_db),
    user: Employee = Depends(get_current_user),
):
    """Most recent payslip on file for the caller. 404 if none yet."""
    payslip = (
        db.query(Payslip)
        .filter(
            Payslip.employee_id == user.id,
            Payslip.deleted_at.is_(None),
        )
        .order_by(Payslip.year.desc(), Payslip.month.desc())
        .first()
    )
    if payslip is None:
        raise HTTPException(404, "No payslip on file yet")
    return {
        "status": status.HTTP_200_OK,
        "message": "Latest payslip fetched",
        "data": PayslipResponse.model_validate(payslip),
    }
