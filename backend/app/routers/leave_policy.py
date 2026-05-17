from fastapi import APIRouter, Depends, Query, status
from sqlalchemy.orm import Session

from app.crud import leave_policy as crud
from app.crud.auth import require_admin
from app.database.database import get_db
from app.schemas.leave import (
    LeavePolicyCreate, LeavePolicyResponse, LeavePolicyUpdate,
)
from app.utils.api_response import ApiResponse, PaginatedResponse

router = APIRouter(tags=["Leave Policies"])


@router.post("/", response_model=ApiResponse[LeavePolicyResponse])
def create_policy(
    data: LeavePolicyCreate,
    db: Session = Depends(get_db),
    user=Depends(require_admin),
):
    return {
        "status": status.HTTP_200_OK,
        "message": "Leave policy created",
        "data": crud.create_leave_policy(db, data, user),
    }


@router.get(
    "/", response_model=ApiResponse[PaginatedResponse[LeavePolicyResponse]]
)
def list_policies(
    db: Session = Depends(get_db),
    skip: int = Query(0, ge=0),
    limit: int = Query(50, ge=1, le=100),
    user=Depends(require_admin),
):
    total, items = crud.list_leave_policies(db, user, skip=skip, limit=limit)
    return {
        "status": status.HTTP_200_OK,
        "message": "Leave policies fetched",
        "data": {"skip": skip, "limit": limit, "total": total, "items": items},
    }


@router.get("/{policy_id}", response_model=ApiResponse[LeavePolicyResponse])
def get_policy(
    policy_id: int,
    db: Session = Depends(get_db),
    user=Depends(require_admin),
):
    return {
        "status": status.HTTP_200_OK,
        "message": "Leave policy fetched",
        "data": crud.get_leave_policy(db, policy_id, user),
    }


@router.put("/{policy_id}", response_model=ApiResponse[LeavePolicyResponse])
def update_policy(
    policy_id: int,
    data: LeavePolicyUpdate,
    db: Session = Depends(get_db),
    user=Depends(require_admin),
):
    return {
        "status": status.HTTP_200_OK,
        "message": "Leave policy updated",
        "data": crud.update_leave_policy(db, policy_id, data, user),
    }


@router.delete("/{policy_id}", response_model=ApiResponse)
def delete_policy(
    policy_id: int,
    db: Session = Depends(get_db),
    user=Depends(require_admin),
):
    crud.delete_leave_policy(db, policy_id, user)
    return {
        "status": status.HTTP_200_OK,
        "message": "Leave policy deleted",
        "data": {},
    }
