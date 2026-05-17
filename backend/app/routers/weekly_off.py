"""Admin CRUD for CompanyWeeklyOff (recurring weekly non-working days).

Lives at /company-weekly-offs/* — separate from /company-holidays/* so
the URL space matches the domain split (explicit dates vs recurring
pattern). The leave + payroll integrations consume the union via
crud.holiday.non_working_dates_in_range in commit 2.
"""
from fastapi import APIRouter, Depends, Query, status
from sqlalchemy.orm import Session

from app.crud import holiday as crud
from app.crud.auth import require_admin
from app.database.database import get_db
from app.schemas.holiday import (
    CompanyWeeklyOffCreate, CompanyWeeklyOffResponse,
)
from app.utils.api_response import ApiResponse

router = APIRouter(tags=["Weekly Offs"])


@router.post("/", response_model=ApiResponse[CompanyWeeklyOffResponse])
def create_weekly_off(
    data: CompanyWeeklyOffCreate,
    db: Session = Depends(get_db),
    user=Depends(require_admin),
):
    return {
        "status": status.HTTP_200_OK,
        "message": "Weekly off created",
        "data": crud.create_weekly_off(db, data, user),
    }


@router.get(
    "/", response_model=ApiResponse[list[CompanyWeeklyOffResponse]]
)
def list_weekly_offs(
    company_id: int | None = Query(None),
    db: Session = Depends(get_db),
    user=Depends(require_admin),
):
    return {
        "status": status.HTTP_200_OK,
        "message": "Weekly offs fetched",
        "data": crud.list_weekly_offs(db, user, company_id=company_id),
    }


@router.delete("/{weekly_off_id}", response_model=ApiResponse)
def delete_weekly_off(
    weekly_off_id: int,
    db: Session = Depends(get_db),
    user=Depends(require_admin),
):
    crud.delete_weekly_off(db, weekly_off_id, user)
    return {
        "status": status.HTTP_200_OK,
        "message": "Weekly off deleted",
        "data": {},
    }
