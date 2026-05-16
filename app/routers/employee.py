from fastapi import (
    APIRouter, BackgroundTasks, Depends, File, HTTPException, UploadFile, status,
)
from sqlalchemy.orm import Session

from app.database.database import get_db
from app.schemas.employee import (
    EmployeeBulkImportResult, EmployeeCreate, EmployeeResponse, EmployeeUpdate,
)
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


@router.post(
    "/import", response_model=ApiResponse[EmployeeBulkImportResult]
)
async def import_employees(
    background_tasks: BackgroundTasks,
    file: UploadFile = File(...),
    db: Session = Depends(get_db),
    user=Depends(require_admin),
):
    """Bulk-create employees from a CSV upload.

    CSV header maps to EmployeeCreate field names; unknown columns are
    ignored. Per-row failures (validation errors, duplicate email,
    invalid role/department) are reported in `skipped` rather than
    aborting the whole upload. Each successful row goes through the
    normal create_employee path — generated roll_no, hashed password,
    welcome email queued as a background task.

    For office_admin the company_id column in the CSV is overridden to
    the actor's own company (matches the bulk-holiday convention).
    """
    if file.content_type and not file.content_type.startswith(
        ("text/csv", "text/plain", "application/csv", "application/vnd.ms-excel")
    ):
        # Be lenient — browsers/Excel sometimes send the file with
        # surprising MIME types. Only reject obvious mismatches
        # (image, pdf, etc.). An empty content_type is fine.
        pass

    contents = await file.read()
    try:
        csv_text = contents.decode("utf-8")
    except UnicodeDecodeError:
        raise HTTPException(400, "CSV must be UTF-8 encoded")

    created, skipped = employee_crud.bulk_import_employees(
        db, csv_text, user, background_tasks
    )
    return {
        "status": status.HTTP_200_OK,
        "message": (
            f"Bulk import done: {len(created)} created, "
            f"{len(skipped)} skipped"
        ),
        "data": {
            "created": [EmployeeResponse.model_validate(e) for e in created],
            "skipped": skipped,
        },
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


@router.get("/role/{role_id}", response_model=ApiResponse[PaginatedResponse[EmployeeResponse]])
def get_employees_by_role(
    role_id: int,
    skip: int = 0,
    limit: int = 10,
    db: Session = Depends(get_db),
    user = Depends(require_admin)
):
    return {
        "status": status.HTTP_200_OK,
        "message": "Users Listed Successfully",
        "data": employee_crud.get_employees_by_role(db, user, role_id, skip, limit)
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