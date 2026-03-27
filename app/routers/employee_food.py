# routers/employee_food.py

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session
from datetime import date
from app.schemas.food import *
from app.crud.food import *
from app.database.database import get_db
from app.crud.auth import require_user

router = APIRouter(tags=["Employee Food"])


@router.get("/menu", response_model=DailyMenuOut)
def get_menu(
    date: date,
    db: Session = Depends(get_db),
    user=Depends(require_user)
):
    return get_menu_by_date(db, date, user.company_id)


@router.post("/select", status_code=201)
def select_food(
    data: FoodSelectionCreate,
    db: Session = Depends(get_db),
    user=Depends(require_user)
):
    return create_food_selection(db, user, data)