# routers/admin_food.py

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session
from datetime import date
from app.schemas.food import *
from app.crud.food import *
from app.database.database import get_db
from app.crud.auth import require_admin
from typing import List

router = APIRouter(tags=["Admin Food"])


@router.post("/item", response_model=FoodItemOut, status_code=201)
def create_item(
    data: FoodItemCreate,
    db: Session = Depends(get_db),
    user=Depends(require_admin)
):
    return create_food_item(db, data)

@router.get("/items", response_model=List[FoodItemOut], status_code=200)
def get_items(
    db: Session = Depends(get_db),
    user=Depends(require_admin)
):
    return get_food_items(db, user)


@router.post("/menu", response_model=DailyMenuOut, status_code=201)
def create_menu(
    data: DailyMenuCreate,
    db: Session = Depends(get_db),
    user=Depends(require_admin)
):
    return create_daily_menu(db, data)


@router.get("/menu", response_model=DailyMenuOut)
def get_menu(
    date: date,
    db: Session = Depends(get_db),
    user=Depends(require_admin)
):
    return get_menu_by_date(db, date)


@router.get("/count", response_model=list[FoodCountOut])
def food_count(
    date: date,
    db: Session = Depends(get_db),
    user=Depends(require_admin)
):
    return get_food_count(db, date)