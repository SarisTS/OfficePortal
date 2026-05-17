from fastapi import APIRouter, Depends, Query, status
from sqlalchemy.orm import Session

from app.crud import leave_balance as crud
from app.crud.auth import get_current_user, require_admin
from app.database.database import get_db
from app.schemas.leave import (
    LeaveBalanceAdjustRequest, LeaveBalanceResponse,
)
from app.services.leave_balance import remaining
from app.utils.api_response import ApiResponse

router = APIRouter(tags=["Leave Balances"])


def _serialize(balance) -> LeaveBalanceResponse:
    """The schema's `remaining` is a derived field, not on the model."""
    return LeaveBalanceResponse(
        id=balance.id,
        employee_id=balance.employee_id,
        year=balance.year,
        leave_type=balance.leave_type,
        allocated=balance.allocated,
        used=balance.used,
        remaining=remaining(balance),
    )


@router.get("/me", response_model=ApiResponse[list[LeaveBalanceResponse]])
def my_balances(
    year: int | None = Query(None),
    db: Session = Depends(get_db),
    user=Depends(get_current_user),
):
    year, items = crud.list_balances_for_employee(db, user.id, user, year)
    return {
        "status": status.HTTP_200_OK,
        "message": f"Leave balances for {year}",
        "data": [_serialize(b) for b in items],
    }


@router.get(
    "/{employee_id}",
    response_model=ApiResponse[list[LeaveBalanceResponse]],
)
def balances_for_employee(
    employee_id: int,
    year: int | None = Query(None),
    db: Session = Depends(get_db),
    user=Depends(require_admin),
):
    year, items = crud.list_balances_for_employee(db, employee_id, user, year)
    return {
        "status": status.HTTP_200_OK,
        "message": f"Leave balances for employee {employee_id} ({year})",
        "data": [_serialize(b) for b in items],
    }


@router.post(
    "/{employee_id}/adjust", response_model=ApiResponse[LeaveBalanceResponse]
)
def adjust(
    employee_id: int,
    data: LeaveBalanceAdjustRequest,
    db: Session = Depends(get_db),
    user=Depends(require_admin),
):
    balance = crud.adjust_balance(db, employee_id, data, user)
    return {
        "status": status.HTTP_200_OK,
        "message": "Leave balance adjusted",
        "data": _serialize(balance),
    }
