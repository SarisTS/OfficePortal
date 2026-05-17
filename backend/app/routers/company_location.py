from fastapi import APIRouter, Depends, Query, status
from sqlalchemy.orm import Session
from app.utils.api_response import ApiResponse, PaginatedResponse
from app.services.company_location_service import CompanyLocationService
from app.schemas.location import CompanyLocationResponse, CompanyLocationCreate, CompanyLocationUpdate
from app.database.database import get_db
from app.crud.auth import require_admin, require_user

router = APIRouter(tags=["Company Locations"])


@router.post("/", response_model=ApiResponse[CompanyLocationResponse])
def create_location(
    data: CompanyLocationCreate,
    db: Session = Depends(get_db),
    user = Depends(require_admin)
):
    result = CompanyLocationService.create_location(db, data, user)

    return {
        "status": status.HTTP_200_OK,
        "message": "Location created",
        "data": result
    }

@router.get("/", response_model=ApiResponse[PaginatedResponse[CompanyLocationResponse]])
def get_locations(
    db: Session = Depends(get_db),
    skip: int = Query(0, ge=0),
    limit: int = Query(10, ge=1, le=100),
    user = Depends(require_user),
):
    total, items = CompanyLocationService.get_locations(db, user, skip=skip, limit=limit)

    return {
        "status": status.HTTP_200_OK,
        "message": "Locations fetched",
        "data": {"skip": skip, "limit": limit, "total": total, "items": items},
    }

@router.get("/{location_id}", response_model=ApiResponse[CompanyLocationResponse])
def get_location(
    location_id: int,
    db: Session = Depends(get_db),
    user = Depends(require_user)
):
    result = CompanyLocationService.get_location(db, location_id, user)

    return {
        "status": status.HTTP_200_OK,
        "message": "Location fetched",
        "data": result
    }

@router.put("/{location_id}", response_model=ApiResponse[CompanyLocationResponse])
def update_location(
    location_id: int,
    data: CompanyLocationUpdate,
    db: Session = Depends(get_db),
    user = Depends(require_admin)
):
    result = CompanyLocationService.update_location(db, location_id, data, user)

    return {
        "status": status.HTTP_200_OK,
        "message": "Location updated",
        "data": result
    }

@router.delete("/{location_id}", response_model=ApiResponse)
def delete_location(
    location_id: int,
    db: Session = Depends(get_db),
    user = Depends(require_admin)
):
    CompanyLocationService.delete_location(db, location_id, user)

    return {
        "status": status.HTTP_200_OK,
        "message": "Location deleted",
        "data": {}
    }