from fastapi import APIRouter, Depends, HTTPException, status, BackgroundTasks
from sqlalchemy.orm import Session

from app.database.database import get_db
from app.schemas.employee import EmployeeCreate, EmployeeUpdate, EmployeeResponse
from app.crud import employee as employee_crud
from app.crud.auth import require_admin
from app.utils.api_response import ApiResponse, PaginatedResponse


router = APIRouter(tags=["Employees"])


@router.post("/", response_model=ApiResponse[EmployeeResponse])
def create_employee(
    employee: EmployeeCreate,
    background_tasks: BackgroundTasks,
    db: Session = Depends(get_db),
    user = Depends(require_admin)
):
    return {
        "status": status.HTTP_200_OK,
        "message": "Employee Created Successfully",
        "data": employee_crud.create_employee(db, employee, user, background_tasks)
    }


@router.get("/", response_model=ApiResponse[PaginatedResponse[EmployeeResponse]])
def get_all_employees(
    skip: int = 0,
    limit: int = 10,
    db: Session = Depends(get_db),
    user = Depends(require_admin)
):
    return {
        "status": status.HTTP_200_OK,
        "message": "Employee Listed Successfully",
        "data": employee_crud.get_all_employees(db, user, skip, limit)
    } 


@router.get("/{employee_id}", response_model=ApiResponse[EmployeeResponse])
def get_employee(
    employee_id: int,
    db: Session = Depends(get_db),
    user = Depends(require_admin)
):
    employee = employee_crud.get_employee(db, employee_id, user)

    if not employee:
        raise HTTPException(404, "Employee not found")

    return {
        "status": status.HTTP_200_OK,
        "message": "Employee Fetched Successfully",
        "data": employee
    }


@router.put("/{employee_id}", response_model=ApiResponse[EmployeeResponse])
def update_employee(
    employee_id: int,
    employee: EmployeeUpdate,
    db: Session = Depends(get_db),
    user = Depends(require_admin)
):
    updated = employee_crud.update_employee(db, employee_id, employee, user)

    if not updated:
        raise HTTPException(404, "Employee not found")

    
    return {
        "status": status.HTTP_200_OK,
        "message": "Employee Updated Successfully",
        "data": updated
    }


@router.delete("/{employee_id}", response_model=ApiResponse)
def delete_employee(
    employee_id: int,
    db: Session = Depends(get_db),
    user = Depends(require_admin)
):
    deleted = employee_crud.delete_employee(db, employee_id, user)

    if not deleted:
        raise HTTPException(404, "Employee not found")

    return {
        "status": status.HTTP_200_OK,
        "message": "Employee deleted successfully",
        "data": {}
    }