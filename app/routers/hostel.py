from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.database.database import get_db
from app.crud import hostel as hostel_crud
from app.crud.auth import require_admin
from app.schemas.hostel import HostelCreate, HostelUpdate, HostelResponse
from app.utils.api_response import ApiResponse

router = APIRouter(tags=["Hostels"])

@router.post("/", response_model=ApiResponse[HostelResponse])
def create_hostel(
    hostel: HostelCreate,
    db: Session = Depends(get_db),
    user = Depends(require_admin)
):
    return {
        "status": status.HTTP_200_OK,
        "message": "Hostel Created successfully",
        "data": hostel_crud.create_hostel(db, hostel, user)
    }


@router.get("/", response_model=ApiResponse[list[HostelResponse]])
def get_hostels(
    skip: int = 0,
    limit: int = 10,
    db: Session = Depends(get_db),
    user = Depends(require_admin)
):
    return {
        "status": status.HTTP_200_OK,
        "message": "Hostel Listed successfully",
        "data": hostel_crud.get_hostels(db, user, skip, limit)
    }


@router.get("/{hostel_id}", response_model=ApiResponse[HostelResponse])
def get_hostel(
    hostel_id: int,
    db: Session = Depends(get_db),
    user = Depends(require_admin)
):
    hostel = hostel_crud.get_hostel(db, hostel_id, user)

    if not hostel:
        raise HTTPException(404, "Hostel not found")

    return {
        "status": status.HTTP_200_OK,
        "message": "Hostel Fetched successfully",
        "data": hostel
    }


@router.put("/{hostel_id}", response_model=ApiResponse[HostelResponse])
def update_hostel(hostel_id: int, hostel: HostelUpdate, db: Session = Depends(get_db), user = Depends(require_admin)):

    updated_hostel = hostel_crud.update_hostel(db, hostel_id, hostel, user)

    if not updated_hostel:
        raise HTTPException(status_code=404, detail="Hostel not found")

    return {
        "status": status.HTTP_200_OK,
        "message": "Hostel Updated successfully",
        "data": updated_hostel
    }


@router.delete("/{hostel_id}", response_model=ApiResponse)
def delete_hostel(hostel_id: int, db: Session = Depends(get_db), user = Depends(require_admin)):

    deleted_hostel = hostel_crud.delete_hostel(db, hostel_id, user)

    if not deleted_hostel:
        raise HTTPException(status_code=404, detail="Hostel not found")

    return {
        "status": status.HTTP_200_OK,
        "message": "Hostel deleted successfully",
        "data": {}
    }