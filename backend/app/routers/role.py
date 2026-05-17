from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.orm import Session

from app.database.database import get_db
from app.schemas.role import RoleCreate, RoleUpdate, RoleResponse
from app.crud import role as role_crud
from app.crud.auth import require_admin
from app.utils.api_response import ApiResponse

router = APIRouter(tags=["Roles"])

# CREATE
@router.post("/", response_model=ApiResponse[RoleResponse])
def create_role(
    role: RoleCreate,
    db: Session = Depends(get_db),
    user = Depends(require_admin)
):
    return {
        "status": status.HTTP_200_OK,
        "message": "Role Created Successfully",
        "data": role_crud.create_role(db, role, user)
    }


# GET ALL
@router.get("/", response_model=ApiResponse[list[RoleResponse]])
def get_roles(
    skip: int = Query(0, ge=0),
    limit: int = Query(10, ge=1, le=100),
    db: Session = Depends(get_db),
    user = Depends(require_admin)
):
    return {
        "status": status.HTTP_200_OK,
        "message": "Role Listed Successfully",
        "data": role_crud.get_roles(db, skip, limit)
    }


# GET ONE
@router.get("/{role_id}", response_model=ApiResponse[RoleResponse])
def get_role(role_id: int, db: Session = Depends(get_db), user = Depends(require_admin)):

    role = role_crud.get_role(db, role_id)

    if not role:
        raise HTTPException(status_code=404, detail="Role not found")

    return {
        "status": status.HTTP_200_OK,
        "message": "Role Fetched Successfully",
        "data": role
    }


# UPDATE
@router.put("/{role_id}", response_model=ApiResponse[RoleResponse])
def update_role(role_id: int, role: RoleUpdate, db: Session = Depends(get_db), user = Depends(require_admin)):

    updated = role_crud.update_role(db, role_id, role, user)

    if not updated:
        raise HTTPException(status_code=404, detail="Role not found")

    return {
        "status": status.HTTP_200_OK,
        "message": "Role Updated Successfully",
        "data": updated
    }


# DELETE
@router.delete("/{role_id}", response_model=ApiResponse)
def delete_role(role_id: int, db: Session = Depends(get_db), user = Depends(require_admin)):

    deleted = role_crud.delete_role(db, role_id, user)

    if not deleted:
        raise HTTPException(status_code=404, detail="Role not found")

    return {
        "status": status.HTTP_200_OK,
        "message": "Role Deleted Successfully",
        "data": {}
    }