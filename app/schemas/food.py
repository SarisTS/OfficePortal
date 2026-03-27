from pydantic import BaseModel
from datetime import date
from typing import List, Optional, Literal


# ---------- Food ----------
class FoodItemCreate(BaseModel):
    name: str
    category: Literal["BREAKFAST", "LUNCH", "DINNER"]


class FoodItemOut(BaseModel):
    id: int
    name: str
    category: str

    class Config:
        orm_mode = True


# ---------- Menu ----------
class DailyMenuCreate(BaseModel):
    date: date
    company_id: Optional[int] = None
    food_item_ids: List[int]


class DailyMenuItemOut(BaseModel):
    food: FoodItemOut

    class Config:
        orm_mode = True


class DailyMenuOut(BaseModel):
    id: int
    date: date
    items: List[DailyMenuItemOut]

    class Config:
        orm_mode = True


# ---------- Selection ----------
class FoodSelectionCreate(BaseModel):
    date: date
    meal_type: Literal["BREAKFAST", "LUNCH", "DINNER"]
    food_item_id: int
    suggestion: Optional[str] = None


# ---------- Count ----------
class FoodCountOut(BaseModel):
    category: str
    food_name: str
    count: int