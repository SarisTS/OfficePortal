# routers/employee_food.py

from fastapi import APIRouter, Depends, status
from sqlalchemy.orm import Session
from datetime import date

from app.schemas.food import DailyMenuOut, FoodSelectionCreate
from app.crud.food import create_food_selection, get_menu_by_date
from app.database.database import get_db
from app.crud.auth import require_user
from app.utils.api_response import ApiResponse

router = APIRouter(tags=["Employee Food"])


# Phase 1 stabilization: both endpoints now wrap responses in the
# standard ApiResponse envelope to match the rest of the API.


@router.get("/menu", response_model=ApiResponse[DailyMenuOut])
def get_menu(
    date: date,
    db: Session = Depends(get_db),
    user=Depends(require_user),
):
    return {
        "status": status.HTTP_200_OK,
        "message": "Daily menu fetched",
        "data": get_menu_by_date(db, date, user.company_id),
    }


@router.post("/select", response_model=ApiResponse)
def select_food(
    data: FoodSelectionCreate,
    db: Session = Depends(get_db),
    user=Depends(require_user),
):
    return {
        "status": status.HTTP_200_OK,
        "message": "Food selection recorded",
        "data": create_food_selection(db, user, data),
    }
