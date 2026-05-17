# routers/admin_food.py

from fastapi import APIRouter, Depends, Query, status
from sqlalchemy.orm import Session
from datetime import date

from app.schemas.food import (
    DailyMenuCreate, DailyMenuOut, FoodCountOut, FoodItemCreate, FoodItemOut,
)
from app.crud.food import (
    create_daily_menu, create_food_item, get_food_count, get_food_items,
    get_menu_by_date,
)
from app.database.database import get_db
from app.crud.auth import require_admin
from app.utils.api_response import ApiResponse, PaginatedResponse

router = APIRouter(tags=["Admin Food"])


# Phase 1 stabilization: every endpoint now returns the standard
# {status, message, data} ApiResponse envelope so a single response
# parser works across the whole API. Previously these returned raw
# schema objects.


@router.post("/item", response_model=ApiResponse[FoodItemOut])
def create_item(
    data: FoodItemCreate,
    db: Session = Depends(get_db),
    user=Depends(require_admin),
):
    return {
        "status": status.HTTP_200_OK,
        "message": "Food item created",
        "data": create_food_item(db, data),
    }


@router.get(
    "/items", response_model=ApiResponse[PaginatedResponse[FoodItemOut]]
)
def get_items(
    db: Session = Depends(get_db),
    skip: int = Query(0, ge=0),
    limit: int = Query(10, ge=1, le=100),
    user=Depends(require_admin),
):
    total, items = get_food_items(db, user, skip=skip, limit=limit)
    return {
        "status": status.HTTP_200_OK,
        "message": "Food items listed",
        "data": {
            "skip": skip,
            "limit": limit,
            "total": total,
            "items": items,
        },
    }


@router.post("/menu", response_model=ApiResponse[DailyMenuOut])
def create_menu(
    data: DailyMenuCreate,
    db: Session = Depends(get_db),
    user=Depends(require_admin),
):
    return {
        "status": status.HTTP_200_OK,
        "message": "Daily menu created",
        "data": create_daily_menu(db, data),
    }


@router.get("/menu", response_model=ApiResponse[DailyMenuOut])
def get_menu(
    date: date,
    db: Session = Depends(get_db),
    user=Depends(require_admin),
):
    return {
        "status": status.HTTP_200_OK,
        "message": "Daily menu fetched",
        "data": get_menu_by_date(db, date),
    }


@router.get("/count", response_model=ApiResponse[list[FoodCountOut]])
def food_count(
    date: date,
    db: Session = Depends(get_db),
    user=Depends(require_admin),
):
    return {
        "status": status.HTTP_200_OK,
        "message": "Food counts fetched",
        "data": get_food_count(db, date),
    }
