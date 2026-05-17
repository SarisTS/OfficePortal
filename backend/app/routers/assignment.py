from fastapi import APIRouter, Depends, Query, status
from sqlalchemy.orm import Session

from app.core.permissions import assert_self_or_admin
from app.database.database import get_db
from app.schemas.assignment import (ShiftAssignmentCreate, ShiftAssignmentResponse, ShiftChangeRequest)
from app.crud import assignment as shift_crud
from app.utils.api_response import ApiResponse, PaginatedResponse
from app.crud.auth import require_admin, require_user
from app.services.shift_assignment_service import ShiftAssignmentService

router = APIRouter(tags=["Shift Assignments"])


@router.post("/", response_model=ApiResponse[ShiftAssignmentResponse])
def assign_shift(
    data: ShiftAssignmentCreate,
    db: Session = Depends(get_db),
    user = Depends(require_admin)
):
    result = ShiftAssignmentService.assign_shift(db, data, user)

    return {
        "status": status.HTTP_200_OK,
        "message": "Shift assigned successfully",
        "data": result
    }


@router.put("/change", response_model=ApiResponse[ShiftAssignmentResponse])
def change_shift(
    data: ShiftChangeRequest,
    db: Session = Depends(get_db),
    user = Depends(require_admin)
):
    result = ShiftAssignmentService.change_shift(
        db,
        data.employee_id,
        data.shift_id,
        data.start_date,
        user
    )

    return {
        "status": status.HTTP_200_OK,
        "message": "Shift changed successfully",
        "data": result
    }

@router.get("/{employee_id}", response_model=ApiResponse[PaginatedResponse[ShiftAssignmentResponse]])
def get_employee_shifts(
    employee_id: int,
    db: Session = Depends(get_db),
    skip: int = Query(0, ge=0),
    limit: int = Query(10, ge=1, le=100),
    user = Depends(require_admin),
):
    # Pass the actor; CRUD enforces same-company for office_admin and global
    # access for super_admin.
    total, items = shift_crud.get_employee_shift_history(
        db, employee_id, user, skip=skip, limit=limit
    )

    return {
        "status": status.HTTP_200_OK,
        "message": "Shift history fetched",
        "data": {"skip": skip, "limit": limit, "total": total, "items": items},
    }


@router.get("/current/{employee_id}", response_model=ApiResponse[ShiftAssignmentResponse])
def get_current_shift(
    employee_id: int,
    db: Session = Depends(get_db),
    user = Depends(require_user)
):
    # Router-level gate: self or any admin. CRUD then enforces same-company
    # for office_admin.
    assert_self_or_admin(user, employee_id)
    result = shift_crud.get_current_shift(db, employee_id, user)

    return {
        "status": status.HTTP_200_OK,
        "message": "Current shift fetched",
        "data": result
    }