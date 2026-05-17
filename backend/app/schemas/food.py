from pydantic import BaseModel, ConfigDict
from datetime import date
from typing import List, Optional, Literal

from app.schemas.base import StrictRequestModel


# ---------- Food ----------
class FoodItemCreate(StrictRequestModel):
    name: str
    category: Literal["BREAKFAST", "LUNCH", "DINNER"]


class FoodItemOut(BaseModel):
    id: int
    name: str
    category: str

    model_config = ConfigDict(from_attributes=True)


# ---------- Menu ----------
class DailyMenuCreate(StrictRequestModel):
    date: date
    company_id: Optional[int] = None
    food_item_ids: List[int]


class DailyMenuItemOut(BaseModel):
    food: FoodItemOut

    model_config = ConfigDict(from_attributes=True)


class DailyMenuOut(BaseModel):
    id: int
    date: date
    items: List[DailyMenuItemOut]

    model_config = ConfigDict(from_attributes=True)


# ---------- Selection ----------
class FoodSelectionCreate(StrictRequestModel):
    date: date
    meal_type: Literal["BREAKFAST", "LUNCH", "DINNER"]
    food_item_id: int
    suggestion: Optional[str] = None


# ---------- Count ----------
class FoodCountOut(BaseModel):
    category: str
    food_name: str
    count: int
