from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.orm import Session

from app.database.database import get_db
from app.schemas.department import *
from app.crud import department as crud
from app.crud.auth import require_admin
from app.utils.api_response import ApiResponse

router = APIRouter(tags=["Departments"])


# CREATE
@router.post("/", response_model=ApiResponse[DepartmentResponse])
def create_department(
    department: DepartmentCreate,
    db: Session = Depends(get_db),
    user = Depends(require_admin)
):
    return {
        "status": status.HTTP_200_OK,
        "message": "Department created successfully",
        "data": crud.create_department(db, department, user)
    }


# GET ALL Departments
@router.get("/", response_model=ApiResponse[list[DepartmentResponse]])
def get_departments(
    skip: int = Query(0, ge=0),
    limit: int = Query(10, ge=1, le=100),
    db: Session = Depends(get_db),
    user = Depends(require_admin)
):
    return {
        "status": status.HTTP_200_OK,
        "message": "Departments listed successfully",
        "data": crud.get_departments(db, user, skip, limit)
    }


# GET Company Departments
@router.get("/company/{company_id}", response_model=ApiResponse[list[DepartmentResponse]])
def get_company_departments(
    company_id: int,
    db: Session = Depends(get_db),
    user = Depends(require_admin)
):
    return {
        "status": status.HTTP_200_OK,
        "message": "Company Departments listed successfully",
        "data": crud.get_company_departments(db, company_id, user)
    }


# UPDATE
@router.put("/{department_id}", response_model=ApiResponse[DepartmentResponse])
def update_department(
    department_id: int,
    data: DepartmentUpdate,
    db: Session = Depends(get_db),
    user = Depends(require_admin)
):
    dept = crud.update_department(db, department_id, data, user)

    if not dept:
        raise HTTPException(404, "Department not found")
    
    return {
        "status": status.HTTP_200_OK,
        "message": "Department Updated successfully",
        "data": dept
    }


# DELETE
@router.delete("/{department_id}", response_model=ApiResponse)
def delete_department(
    department_id: int,
    db: Session = Depends(get_db),
    user = Depends(require_admin)
):
    dept = crud.delete_department(db, department_id, user)

    if not dept:
        raise HTTPException(404, "Department not found")

    return {
        "status": status.HTTP_200_OK,
        "message": "Department Deleted successfully",
        "data": {}
    }


