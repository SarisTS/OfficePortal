"""Endpoints scoped to the authenticated user (self-service).

The /me/* namespace is for things the user does to their OWN account.
Anything admin-mediated belongs in the matching resource router instead
(/employees/{id}, etc.). Today: profile read + edit. Future candidates
that fit here: /me/avatar, /me/preferences, /me/sessions.
"""
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.crud.auth import get_current_user
from app.crud.employee import update_own_profile
from app.crud.salary_structure import get_current_structure
from app.database.database import get_db
from app.models.employee import Employee
from app.schemas.employee import EmployeeResponse, ProfileUpdate
from app.schemas.payslip import SalaryStructureResponse
from app.utils.api_response import ApiResponse

router = APIRouter(tags=["Me"])


@router.get("/profile", response_model=ApiResponse[EmployeeResponse])
def get_my_profile(user: Employee = Depends(get_current_user)):
    """Read the authenticated user's profile.

    Same sanitization as /auth/me — password_hash and google_id are not
    in EmployeeResponse so they cannot leak through this projection.
    """
    return {
        "status": status.HTTP_200_OK,
        "message": "Profile fetched",
        "data": EmployeeResponse.model_validate(user),
    }


@router.put("/profile", response_model=ApiResponse[EmployeeResponse])
def update_my_profile(
    data: ProfileUpdate,
    db: Session = Depends(get_db),
    user: Employee = Depends(get_current_user),
):
    """Self-service edit. Whitelist + uniqueness pre-check lives in
    crud.employee.update_own_profile."""
    updated = update_own_profile(db, user, data)
    return {
        "status": status.HTTP_200_OK,
        "message": "Profile updated",
        "data": EmployeeResponse.model_validate(updated),
    }


@router.get("/salary", response_model=ApiResponse[SalaryStructureResponse])
def get_my_current_salary(
    db: Session = Depends(get_db),
    user: Employee = Depends(get_current_user),
):
    """Return the SalaryStructure active for the caller today.

    404 if the caller has no structure on file yet (admin hasn't created
    one). Past structures aren't surfaced here — for history, admins
    can read via GET /salary-structures/employee/{id}.
    """
    structure = get_current_structure(db, user.id)
    if structure is None:
        raise HTTPException(404, "No active salary structure on file")
    return {
        "status": status.HTTP_200_OK,
        "message": "Current salary structure",
        "data": SalaryStructureResponse.model_validate(structure),
    }
