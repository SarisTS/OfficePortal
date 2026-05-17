from datetime import date

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.orm import Session

from app.core.permissions import assert_can_access_employee
from app.database.database import get_db
from app.crud import attendance as attendance_crud
from app.crud.auth import require_user, require_admin
from app.models.attendance import Attendance

from app.schemas.attendance import (AttendanceResponse, AttendanceUpdate, ManualAttendanceCreate,
     CheckInRequest, CheckOutRequest)
from app.utils.api_response import ApiResponse
from app.services.attendance_service import AttendanceService

router = APIRouter(tags=["Attendance"])

@router.post("/check-in", response_model=ApiResponse[AttendanceResponse])
def check_in(
    data: CheckInRequest,
    db: Session = Depends(get_db),
    user = Depends(require_user)
):
    attendance = AttendanceService.check_in(
        db,
        user,
        data.lat,
        data.lon
    )

    return {
        "status": status.HTTP_200_OK,
        "message": "Attendance Checked In",
        "data": AttendanceResponse.model_validate(attendance)
    }


@router.post("/check-out", response_model=ApiResponse[AttendanceResponse])
def check_out(
    data: CheckOutRequest,
    db: Session = Depends(get_db),
    user = Depends(require_user)
):
    attendance = AttendanceService.check_out(
        db,
        user,
        data.lat,
        data.lon
    )

    return {
        "status": status.HTTP_200_OK,
        "message": "Attendance Checked Out",
        "data": AttendanceResponse.model_validate(attendance)
    }


@router.get("/me", response_model=ApiResponse[list[AttendanceResponse]])
def get_my_attendance(
    year: int | None = Query(None, ge=2000, le=2100),
    month: int | None = Query(None, ge=1, le=12),
    from_date: date | None = Query(None),
    to_date: date | None = Query(None),
    db: Session = Depends(get_db),
    user = Depends(require_user)
):
    """The caller's own attendance ledger.

    Phase 1: optional filters for the mobile calendar view. Previously
    returned the full multi-year history per request, which is wasteful
    on mobile data.

      - `year` + `month`  → calendar-month view (most common)
      - `year` alone      → full year
      - `from_date`/`to_date` → explicit window (inclusive both ends)

    `month` requires `year`. `from_date`/`to_date` are mutually
    exclusive with `year`/`month`.
    """
    if month is not None and year is None:
        raise HTTPException(400, "month filter requires year")
    if (from_date or to_date) and (year is not None or month is not None):
        raise HTTPException(
            400,
            "Use either year/month OR from_date/to_date, not both",
        )

    query = db.query(Attendance).filter(
        Attendance.employee_id == user.id,
        Attendance.deleted_at.is_(None),
    )

    if year is not None:
        if month is None:
            query = query.filter(
                Attendance.date >= date(year, 1, 1),
                Attendance.date <= date(year, 12, 31),
            )
        else:
            from calendar import monthrange
            _, last = monthrange(year, month)
            query = query.filter(
                Attendance.date >= date(year, month, 1),
                Attendance.date <= date(year, month, last),
            )
    if from_date is not None:
        query = query.filter(Attendance.date >= from_date)
    if to_date is not None:
        query = query.filter(Attendance.date <= to_date)

    items = query.order_by(Attendance.date.desc()).all()
    return {
        "status": status.HTTP_200_OK,
        "message": "Attendance fetched",
        "data": items,
    }


@router.get("/employee/{employee_id}", response_model=ApiResponse[list[AttendanceResponse]])
def get_employee_attendance(
    employee_id: int,
    db: Session = Depends(get_db),
    user = Depends(require_admin)
):
    data = attendance_crud.get_employee_attendance(db, employee_id, user)

    return {
        "status": status.HTTP_200_OK,
        "message": "Employee attendance fetched",
        "data": data
    }


@router.get("/{attendance_id}", response_model=ApiResponse[AttendanceResponse])
def get_attendance(
    attendance_id: int,
    db: Session = Depends(get_db),
    user = Depends(require_user)
):
    attendance = attendance_crud.get_attendance(db, attendance_id, user)

    if not attendance:
        raise HTTPException(404, "Attendance not found")

    return {
        "status": status.HTTP_200_OK,
        "message": "Attendance fetched",
        "data": attendance
    }


@router.put("/{attendance_id}", response_model=ApiResponse[AttendanceResponse])
def update_attendance(
    attendance_id: int,
    data: AttendanceUpdate,
    db: Session = Depends(get_db),
    user = Depends(require_admin)
):
    updated = attendance_crud.update_attendance(
        db,
        attendance_id,
        data,
        user
    )

    if not updated:
        raise HTTPException(404, "Attendance not found")

    return {
        "status": status.HTTP_200_OK,
        "message": "Attendance updated",
        "data": updated
    }


@router.delete("/{attendance_id}", response_model=ApiResponse)
def delete_attendance(
    attendance_id: int,
    db: Session = Depends(get_db),
    user = Depends(require_admin)
):
    deleted = attendance_crud.delete_attendance(db, attendance_id, user)

    if not deleted:
        raise HTTPException(404, "Attendance not found")

    return {
        "status": status.HTTP_200_OK,
        "message": "Attendance deleted",
        "data": {}
    }


@router.post(
    "/manual/{employee_id}",
    response_model=ApiResponse[AttendanceResponse],
)
def mark_manual_attendance(
    employee_id: int,
    data: ManualAttendanceCreate,
    db: Session = Depends(get_db),
    user = Depends(require_admin),
):
    """Admin-only manual attendance marking.

    Phase 1 rewrite: `employee_id` is now in the path and `date` lives
    inside the body schema (ManualAttendanceCreate). Previously both were
    unannotated function parameters, which FastAPI silently treated as
    query strings.

    Tenant scoping: `assert_can_access_employee` gates the actor at the
    router boundary; the CRUD layer also re-checks, so a defense-in-depth
    cross-tenant attempt fails twice.
    """
    assert_can_access_employee(db, employee_id, user)
    attendance = attendance_crud.mark_manual_attendance(
        db,
        employee_id,
        data.date,
        data,
        user,
    )

    return {
        "status": status.HTTP_200_OK,
        "message": "Manual attendance marked",
        "data": attendance,
    }