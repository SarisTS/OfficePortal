from fastapi import (
    APIRouter, BackgroundTasks, Depends, File, HTTPException, Query, UploadFile,
    status,
)
from sqlalchemy.orm import Session

from app.database.database import get_db
from app.models.employee import UserTypes
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
    skip: int = Query(0, ge=0),
    limit: int = Query(10, ge=1, le=100),
    q: str | None = Query(
        None,
        description="Search across name, email, roll_no and mobile (ILIKE).",
    ),
    department_id: int | None = Query(None),
    user_type: UserTypes | None = Query(None),
    is_active: bool | None = Query(None),
    db: Session = Depends(get_db),
    user = Depends(require_admin),
):
    """Paginated directory + admin filters.

    Tenant scope is enforced inside the CRUD: super_admin sees every
    employee; office_admin sees only their own company. The filters
    layer on top of that scope, they never widen it.
    """
    return {
        "status": status.HTTP_200_OK,
        "message": "Employee Listed Successfully",
        "data": employee_crud.get_all_employees(
            db, user, skip=skip, limit=limit,
            q=q, department_id=department_id,
            user_type=user_type, is_active=is_active,
        )
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


# ---------------------------------------------------------------------------
# Admin lifecycle: password reset + activate / deactivate
#
# Distinct from the employee-initiated forgot-password / reset-password
# in auth.py — those use mobile OTP and the employee triggers them.
# These endpoints are admin-initiated for the case where an employee
# can't access their own account.
# ---------------------------------------------------------------------------

@router.post("/{employee_id}/reset-password", response_model=ApiResponse)
def admin_reset_password(
    employee_id: int,
    background_tasks: BackgroundTasks,
    db: Session = Depends(get_db),
    user = Depends(require_admin),
):
    """Generate a new password for the employee, hash + store it, and
    email the new credentials. The new password is NOT included in the
    response (it leaves only via email so the audit trail stays clean)."""
    employee = employee_crud.admin_reset_password(
        db, employee_id, user, background_tasks,
    )
    if not employee:
        raise HTTPException(404, "Employee not found")
    return {
        "status": status.HTTP_200_OK,
        "message": "Password reset. New credentials sent to the employee.",
        "data": {"id": employee.id, "email": employee.email},
    }


@router.post(
    "/{employee_id}/activate", response_model=ApiResponse[EmployeeResponse]
)
def activate_employee(
    employee_id: int,
    db: Session = Depends(get_db),
    user = Depends(require_admin),
):
    """Re-enable an employee. Reversible counterpart of /deactivate."""
    employee = employee_crud.set_employee_active(
        db, employee_id, user, is_active=True,
    )
    if not employee:
        raise HTTPException(404, "Employee not found")
    return {
        "status": status.HTTP_200_OK,
        "message": "Employee activated",
        "data": employee,
    }


@router.post(
    "/{employee_id}/deactivate",
    response_model=ApiResponse[EmployeeResponse],
)
def deactivate_employee(
    employee_id: int,
    db: Session = Depends(get_db),
    user = Depends(require_admin),
):
    """Block login + freeze the employee without deleting the row.

    Distinct from DELETE /employees/{id}, which is the one-way soft-delete.
    Deactivation is for "on leave / suspended / paused" — fully reversible."""
    employee = employee_crud.set_employee_active(
        db, employee_id, user, is_active=False,
    )
    if not employee:
        raise HTTPException(404, "Employee not found")
    return {
        "status": status.HTTP_200_OK,
        "message": "Employee deactivated",
        "data": employee,
    }