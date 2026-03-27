from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.database.database import get_db
from app.crud import leave as leave_crud
from app.schemas.leave import LeaveCreate, LeaveUpdate, LeaveResponse
from app.crud.auth import require_user, require_admin
from app.utils.api_response import ApiResponse

router = APIRouter(tags=["Leaves"])


@router.post("/", response_model=ApiResponse[LeaveResponse])
def create_leave(
    leave: LeaveCreate,
    db: Session = Depends(get_db),
    user = Depends(require_user)
):
    return {
        "status": status.HTTP_200_OK,
        "message": "Leave created successfully",
        "data": leave_crud.create_leave(db, leave, user)
    }


@router.get("/", response_model=ApiResponse[list[LeaveResponse]])
def get_leaves(
    skip: int = 0,
    limit: int = 10,
    db: Session = Depends(get_db),
    user = Depends(require_user)
):
    return {
        "status": status.HTTP_200_OK,
        "message": "Leaves fetched successfully",
        "data": leave_crud.get_leaves(db, user, skip, limit)
    }


@router.get("/employee/{employee_id}", response_model=ApiResponse[list[LeaveResponse]])
def get_employee_leaves(
    employee_id: int,
    db: Session = Depends(get_db),
    user = Depends(require_user)
):
    return {
        "status": status.HTTP_200_OK,
        "message": "Employee leaves fetched",
        "data": leave_crud.get_employee_leaves(db, employee_id, user)
    }


@router.get("/{leave_id}", response_model=ApiResponse[LeaveResponse])
def get_leave(
    leave_id: int,
    db: Session = Depends(get_db),
    user = Depends(require_user)
):
    leave = leave_crud.get_leave(db, leave_id, user)

    if not leave:
        raise HTTPException(404, "Leave not found")

    return {
        "status": status.HTTP_200_OK,
        "message": "Leave fetched",
        "data": leave
    }


@router.put("/{leave_id}", response_model=ApiResponse[LeaveResponse])
def update_leave(
    leave_id: int,
    leave: LeaveUpdate,
    db: Session = Depends(get_db),
    user = Depends(require_user)
):
    updated = leave_crud.update_leave(db, leave_id, leave, user)

    if not updated:
        raise HTTPException(404, "Leave not found")

    return {
        "status": status.HTTP_200_OK,
        "message": "Leave updated successfully",
        "data": updated
    }


@router.delete("/{leave_id}", response_model=ApiResponse)
def delete_leave(
    leave_id: int,
    db: Session = Depends(get_db),
    user = Depends(require_user)
):
    deleted = leave_crud.delete_leave(db, leave_id, user)

    if not deleted:
        raise HTTPException(404, "Leave not found")

    return {
        "status": status.HTTP_200_OK,
        "message": "Leave deleted successfully",
        "data": {}
    }


# 🔥 NEW APIs

@router.post("/{leave_id}/approve", response_model=ApiResponse[LeaveResponse])
def approve_leave(
    leave_id: int,
    db: Session = Depends(get_db),
    user = Depends(require_admin)
):
    return {
        "status": status.HTTP_200_OK,
        "message": "Leave approved",
        "data": leave_crud.approve_leave(db, leave_id, user)
    }


@router.post("/{leave_id}/reject", response_model=ApiResponse[LeaveResponse])
def reject_leave(
    leave_id: int,
    db: Session = Depends(get_db),
    user = Depends(require_admin)
):
    return {
        "status": status.HTTP_200_OK,
        "message": "Leave rejected",
        "data": leave_crud.reject_leave(db, leave_id, user)
    }