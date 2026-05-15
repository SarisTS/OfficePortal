from fastapi import APIRouter, Depends, status
from app.utils.api_response import ApiResponse
from app.services.shift_service import ShiftService
from app.schemas.assignment import ShiftCreate, ShiftResponse, ShiftUpdate
from sqlalchemy.orm import Session
from app.database.database import get_db
from app.crud.auth import require_admin


router = APIRouter(tags=["Shifts"])

@router.post("/", response_model=ApiResponse[ShiftResponse])
def create_shift(
    shift: ShiftCreate,
    db: Session = Depends(get_db),
    user = Depends(require_admin)
):
    result= ShiftService.create_shift(db, shift, user)

    return{
        "status": status.HTTP_200_OK,
        "message": "Shift created successfully",
        "data": result
    }

@router.get("/", response_model=ApiResponse[list[ShiftResponse]])
def get_shifts(
    db: Session = Depends(get_db),
    user = Depends(require_admin)
):
    result = ShiftService.get_shifts(db, user)

    return {
        "status": status.HTTP_200_OK,
        "message": "Shifts Listed successfully",
        "data": result
    }


@router.get("/{shift_id}", response_model=ApiResponse[ShiftResponse])
def get_shift(
    shift_id: int,
    db: Session = Depends(get_db),
    user = Depends(require_admin)
):
    result = ShiftService.get_shift(db, shift_id, user)

    return {
        "status": status.HTTP_200_OK,
        "message": "Shift fetched successfully",
        "data": result
    }

@router.get("/company/{company_id}", response_model=ApiResponse[list[ShiftResponse]])
def get_shifts_by_company(
    company_id: int,
    db: Session = Depends(get_db),
    user = Depends(require_admin)
):
    result = ShiftService.get_shifts_by_company(db, company_id, user)

    return {
        "status": status.HTTP_200_OK,
        "message": "Shifts listed for this company successfully",
        "data": result
    }


@router.put("/{shift_id}", response_model=ApiResponse[ShiftResponse])
def update_shift(
    shift_id: int,
    shift: ShiftUpdate,
    db: Session = Depends(get_db),
    user = Depends(require_admin)
):
    result = ShiftService.update_shift(db, shift_id, shift, user)

    return {
        "status": status.HTTP_200_OK,
        "message": "Shift updated successfully",
        "data": result
    }


@router.delete("/{shift_id}", response_model=ApiResponse)
def delete_shift(
    shift_id: int,
    db: Session = Depends(get_db),
    user = Depends(require_admin)
):
    ShiftService.delete_shift(db, shift_id, user)

    return {
        "status": status.HTTP_200_OK,
        "message": "Shift deleted successfully",
        "data": {}
    }