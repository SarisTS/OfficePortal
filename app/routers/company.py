from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from app.database.database import get_db
from app.crud import company as crud
from app.crud.auth import require_admin, require_super_admin
from app.schemas.company import CompanyCreate, CompanyUpdate, CompanyResponse
from app.utils.api_response import ApiResponse

router = APIRouter(tags=["Companies"])


# Mutations are super_admin only. office_admin shouldn't be able to
# create sibling tenants, rename them, or soft-delete them — those are
# global operations.
@router.post("/", response_model=ApiResponse[CompanyResponse])
def create_company(
    company: CompanyCreate,
    db: Session = Depends(get_db),
    user = Depends(require_super_admin)
):
    return {
        "status": status.HTTP_200_OK,
        "message": "Company created successfully",
        "data": crud.create_company(db, company, user.id)
    }


# Reads stay open to any admin, but the CRUD layer scopes the result to
# the actor's own company unless they're super_admin.
@router.get("/", response_model=ApiResponse[list[CompanyResponse]])
def get_companies(
    skip: int = 0,
    limit: int = 10,
    name: str = None,
    db: Session = Depends(get_db),
    user = Depends(require_admin)
):
    return {
        "status": status.HTTP_200_OK,
        "message": "Companies Listed successfully",
        "data": crud.get_companies(db, user, skip, limit, name)
    }



@router.get("/{company_id}", response_model=ApiResponse[CompanyResponse])
def get_company(
    company_id: int,
    db: Session = Depends(get_db),
    user = Depends(require_admin)
):
    company = crud.get_company(db, company_id, user)

    if not company:
        raise HTTPException(status_code=404, detail="Company not found")

    return {
        "status": status.HTTP_200_OK,
        "message": "Company Fetched successfully",
        "data": company
    }


@router.put("/{company_id}", response_model=ApiResponse[CompanyResponse])
def update_company(
    company_id: int,
    company: CompanyUpdate,
    db: Session = Depends(get_db),
    user = Depends(require_super_admin)
):
    updated = crud.update_company(db, company_id, company, user.id)

    if not updated:
        raise HTTPException(status_code=404, detail="Company not found")

    return {
        "status": status.HTTP_200_OK,
        "message": "Company Updated successfully",
        "data": updated
    }


@router.delete("/{company_id}", response_model=ApiResponse)
def delete_company(
    company_id: int,
    db: Session = Depends(get_db),
    user = Depends(require_super_admin)
):
    deleted = crud.delete_company(db, company_id, user.id)

    if not deleted:
        raise HTTPException(status_code=404, detail="Company not found")

    return {
        "status": status.HTTP_200_OK,
        "message": "Company Deleted successfully",
        "data": {}
    }
