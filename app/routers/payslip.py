from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.orm import Session

from app.core.permissions import (
    assert_can_access_employee, is_super_admin,
)
from app.crud.auth import get_current_user, require_admin
from app.database.database import get_db
from app.models.payslip import Payslip
from app.schemas.payslip import PayslipGenerateRequest, PayslipResponse
from app.services.payroll import generate_for_company, generate_payslip
from app.utils.api_response import ApiResponse

router = APIRouter(tags=["Payslips"])


# ---------------------------------------------------------------------------
# Generation
# ---------------------------------------------------------------------------

@router.post(
    "/employee/{employee_id}/generate",
    response_model=ApiResponse[PayslipResponse],
)
def generate_single(
    employee_id: int,
    data: PayslipGenerateRequest,
    db: Session = Depends(get_db),
    user=Depends(require_admin),
):
    """Generate a payslip for one employee for the given period.

    Tenant-checks the target via assert_can_access_employee (super_admin
    unscoped, office_admin same-company). The service then enforces the
    data-side invariants (no double-generate, active structure required).
    """
    target = assert_can_access_employee(db, employee_id, user)
    payslip = generate_payslip(db, target.id, data.year, data.month, user)
    return {
        "status": status.HTTP_200_OK,
        "message": f"Payslip generated for {data.year}-{data.month:02d}",
        "data": payslip,
    }


@router.post(
    "/company/{company_id}/generate",
    response_model=ApiResponse,
)
def generate_bulk(
    company_id: int,
    data: PayslipGenerateRequest,
    db: Session = Depends(get_db),
    user=Depends(require_admin),
):
    """Bulk-generate for every staff/employee in the company.

    Each individual employee's failure (missing structure, payslip
    already exists for the period) is captured in the `skipped` list
    rather than aborting the run.
    """
    if not is_super_admin(user) and user.company_id != company_id:
        raise HTTPException(
            403, "Cannot generate payslips for another company"
        )

    generated, skipped = generate_for_company(
        db, company_id, data.year, data.month, user
    )
    return {
        "status": status.HTTP_200_OK,
        "message": (
            f"Bulk generation done: {len(generated)} generated, "
            f"{len(skipped)} skipped"
        ),
        "data": {
            "generated": [
                PayslipResponse.model_validate(p) for p in generated
            ],
            "skipped": skipped,
        },
    }


# ---------------------------------------------------------------------------
# Reads
# ---------------------------------------------------------------------------

@router.get("/me", response_model=ApiResponse[list[PayslipResponse]])
def list_my_payslips(
    year: int | None = Query(None),
    month: int | None = Query(None),
    db: Session = Depends(get_db),
    user=Depends(get_current_user),
):
    """Self-service list. Optional year and/or month filters."""
    query = db.query(Payslip).filter(
        Payslip.employee_id == user.id,
        Payslip.deleted_at.is_(None),
    )
    if year is not None:
        query = query.filter(Payslip.year == year)
    if month is not None:
        query = query.filter(Payslip.month == month)
    items = (
        query.order_by(Payslip.year.desc(), Payslip.month.desc()).all()
    )
    return {
        "status": status.HTTP_200_OK,
        "message": "Payslips fetched",
        "data": items,
    }


@router.get(
    "/employee/{employee_id}",
    response_model=ApiResponse[list[PayslipResponse]],
)
def list_employee_payslips(
    employee_id: int,
    year: int | None = Query(None),
    db: Session = Depends(get_db),
    user=Depends(require_admin),
):
    """Admin: read all of one employee's payslips."""
    target = assert_can_access_employee(db, employee_id, user)
    query = db.query(Payslip).filter(
        Payslip.employee_id == target.id,
        Payslip.deleted_at.is_(None),
    )
    if year is not None:
        query = query.filter(Payslip.year == year)
    items = (
        query.order_by(Payslip.year.desc(), Payslip.month.desc()).all()
    )
    return {
        "status": status.HTTP_200_OK,
        "message": "Employee payslips fetched",
        "data": items,
    }


@router.get(
    "/{payslip_id}", response_model=ApiResponse[PayslipResponse]
)
def get_payslip(
    payslip_id: int,
    db: Session = Depends(get_db),
    user=Depends(get_current_user),
):
    """Read a single payslip. Self can read own; admin can read any
    employee in their scope."""
    payslip = db.query(Payslip).filter(
        Payslip.id == payslip_id,
        Payslip.deleted_at.is_(None),
    ).first()
    if not payslip:
        raise HTTPException(404, "Payslip not found")

    # Single check handles both branches:
    #   - if caller IS the employee, this returns the row
    #   - otherwise the caller must be an admin scoped to the target's
    #     company, else 403
    assert_can_access_employee(db, payslip.employee_id, user)
    return {
        "status": status.HTTP_200_OK,
        "message": "Payslip fetched",
        "data": payslip,
    }
