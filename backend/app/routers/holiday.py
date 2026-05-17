from fastapi import APIRouter, Depends, Query, status
from sqlalchemy.orm import Session

from app.crud import holiday as crud
from app.crud.auth import require_admin
from app.database.database import get_db
from app.schemas.holiday import (
    CompanyHolidayBulkCreate, CompanyHolidayBulkDelete,
    CompanyHolidayBulkDeleteResult, CompanyHolidayBulkResult,
    CompanyHolidayCreate, CompanyHolidayResponse, CompanyHolidayUpdate,
)
from app.utils.api_response import ApiResponse

router = APIRouter(tags=["Holidays"])


@router.post("/", response_model=ApiResponse[CompanyHolidayResponse])
def create_holiday(
    data: CompanyHolidayCreate,
    db: Session = Depends(get_db),
    user=Depends(require_admin),
):
    return {
        "status": status.HTTP_200_OK,
        "message": "Holiday created",
        "data": crud.create_holiday(db, data, user),
    }


@router.post(
    "/bulk", response_model=ApiResponse[CompanyHolidayBulkResult]
)
def bulk_create(
    data: CompanyHolidayBulkCreate,
    db: Session = Depends(get_db),
    user=Depends(require_admin),
):
    """Create many holidays in one call. Per-row failures (mostly
    duplicates) are reported in `skipped` rather than aborting."""
    company_id = crud._resolve_company_id(user, data.company_id)
    created, skipped = crud.bulk_create_holidays(
        db, company_id, data.holidays, user
    )
    return {
        "status": status.HTTP_200_OK,
        "message": (
            f"Bulk create done: {len(created)} created, "
            f"{len(skipped)} skipped"
        ),
        "data": {"created": created, "skipped": skipped},
    }


@router.get(
    "/", response_model=ApiResponse[list[CompanyHolidayResponse]]
)
def list_holidays(
    company_id: int | None = Query(None),
    year: int | None = Query(None, ge=2000, le=2100),
    month: int | None = Query(None, ge=1, le=12),
    db: Session = Depends(get_db),
    user=Depends(require_admin),
):
    items = crud.list_holidays(
        db, user, company_id=company_id, year=year, month=month
    )
    return {
        "status": status.HTTP_200_OK,
        "message": "Holidays fetched",
        "data": items,
    }


@router.get(
    "/{holiday_id}", response_model=ApiResponse[CompanyHolidayResponse]
)
def get_holiday(
    holiday_id: int,
    db: Session = Depends(get_db),
    user=Depends(require_admin),
):
    return {
        "status": status.HTTP_200_OK,
        "message": "Holiday fetched",
        "data": crud.get_holiday(db, holiday_id, user),
    }


@router.put(
    "/{holiday_id}", response_model=ApiResponse[CompanyHolidayResponse]
)
def update_holiday(
    holiday_id: int,
    data: CompanyHolidayUpdate,
    db: Session = Depends(get_db),
    user=Depends(require_admin),
):
    return {
        "status": status.HTTP_200_OK,
        "message": "Holiday updated",
        "data": crud.update_holiday(db, holiday_id, data, user),
    }


@router.delete(
    "/bulk", response_model=ApiResponse[CompanyHolidayBulkDeleteResult]
)
def bulk_delete(
    data: CompanyHolidayBulkDelete,
    db: Session = Depends(get_db),
    user=Depends(require_admin),
):
    """Delete many holidays in one call.

    Two modes (caller supplies exactly one):
      - `ids`: specific holiday IDs to remove (surgical)
      - `year`: clear every holiday in the company for that year
                (typical: re-upload after a wrong import)

    Tenant-scope-resolved company_id keeps office_admin from acting on
    another tenant's data. Each successful delete writes a holiday.delete
    audit row.
    """
    company_id = crud._resolve_company_id(user, data.company_id)
    deleted, skipped = crud.bulk_delete_holidays(
        db, company_id, user, ids=data.ids, year=data.year,
    )
    return {
        "status": status.HTTP_200_OK,
        "message": f"Bulk delete done: {deleted} deleted, {len(skipped)} skipped",
        "data": {"deleted": deleted, "skipped": skipped},
    }


@router.delete("/{holiday_id}", response_model=ApiResponse)
def delete_holiday(
    holiday_id: int,
    db: Session = Depends(get_db),
    user=Depends(require_admin),
):
    crud.delete_holiday(db, holiday_id, user)
    return {
        "status": status.HTTP_200_OK,
        "message": "Holiday deleted",
        "data": {},
    }
