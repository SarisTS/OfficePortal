from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from datetime import datetime

from app.database.database import get_db
from app.crud import attendance as attendance_crud
from app.crud.auth import require_user, require_admin

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
    db: Session = Depends(get_db),
    user = Depends(require_user)
):
    data = attendance_crud.get_employee_attendance(db, user.id, user)

    return {
        "status": status.HTTP_200_OK,
        "message": "Attendance fetched",
        "data": data
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


@router.post("/manual", response_model=ApiResponse[AttendanceResponse])
def mark_manual_attendance(
    employee_id: int,
    date: datetime,
    data: ManualAttendanceCreate,
    db: Session = Depends(get_db),
    user = Depends(require_admin)
):
    attendance = attendance_crud.mark_manual_attendance(
        db,
        employee_id,
        date,
        data,
        user
    )

    return {
        "status": status.HTTP_200_OK,
        "message": "Manual attendance marked",
        "data": attendance
    }