from fastapi import APIRouter, Depends, Query, status
from sqlalchemy.orm import Session

from app.crud import salary_structure as crud
from app.crud.auth import require_admin
from app.database.database import get_db
from app.schemas.payslip import (
    SalaryStructureCreate, SalaryStructureResponse, SalaryStructureUpdate,
)
from app.utils.api_response import ApiResponse, PaginatedResponse

router = APIRouter(tags=["Salary Structures"])


@router.post("/", response_model=ApiResponse[SalaryStructureResponse])
def create_structure(
    data: SalaryStructureCreate,
    db: Session = Depends(get_db),
    user=Depends(require_admin),
):
    return {
        "status": status.HTTP_200_OK,
        "message": "Salary structure created",
        "data": crud.create_structure(db, data, user),
    }


@router.get(
    "/employee/{employee_id}",
    response_model=ApiResponse[PaginatedResponse[SalaryStructureResponse]],
)
def list_for_employee(
    employee_id: int,
    db: Session = Depends(get_db),
    skip: int = Query(0, ge=0),
    limit: int = Query(50, ge=1, le=100),
    user=Depends(require_admin),
):
    total, items = crud.list_structures_for_employee(
        db, employee_id, user, skip=skip, limit=limit
    )
    return {
        "status": status.HTTP_200_OK,
        "message": "Salary structures fetched",
        "data": {"skip": skip, "limit": limit, "total": total, "items": items},
    }


@router.get(
    "/{structure_id}", response_model=ApiResponse[SalaryStructureResponse]
)
def get_structure(
    structure_id: int,
    db: Session = Depends(get_db),
    user=Depends(require_admin),
):
    return {
        "status": status.HTTP_200_OK,
        "message": "Salary structure fetched",
        "data": crud.get_structure(db, structure_id, user),
    }


@router.put(
    "/{structure_id}", response_model=ApiResponse[SalaryStructureResponse]
)
def update_structure(
    structure_id: int,
    data: SalaryStructureUpdate,
    db: Session = Depends(get_db),
    user=Depends(require_admin),
):
    return {
        "status": status.HTTP_200_OK,
        "message": "Salary structure updated",
        "data": crud.update_structure(db, structure_id, data, user),
    }


@router.delete("/{structure_id}", response_model=ApiResponse)
def delete_structure(
    structure_id: int,
    db: Session = Depends(get_db),
    user=Depends(require_admin),
):
    crud.delete_structure(db, structure_id, user)
    return {
        "status": status.HTTP_200_OK,
        "message": "Salary structure deleted",
        "data": {},
    }
