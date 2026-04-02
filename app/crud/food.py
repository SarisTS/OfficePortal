from sqlalchemy.orm import Session
from datetime import datetime
from fastapi import HTTPException
from sqlalchemy import or_, text
from app.crud.auth import is_global_admin
from app.models.food import FoodItem, DailyMenu, DailyMenuItem, FoodSelection


# ---------- ADMIN ----------

def create_food_item(db: Session, data):
    food = FoodItem(**data.dict())
    db.add(food)
    db.commit()
    db.refresh(food)
    return food


def create_daily_menu(db: Session, data):
    existing = db.query(DailyMenu).filter(
        DailyMenu.date == data.date,
        DailyMenu.company_id == data.company_id
    ).first()

    if existing:
        raise HTTPException(400, "Menu already exists")

    menu = DailyMenu(date=data.date, company_id=data.company_id)
    db.add(menu)
    db.commit()
    db.refresh(menu)

    for fid in data.food_item_ids:
        db.add(DailyMenuItem(daily_menu_id=menu.id, food_item_id=fid))

    db.commit()
    return menu

def get_food_items(db: Session, user):
    if not is_global_admin(user):
        raise HTTPException(403, "Not authorized")

    return db.query(FoodItem).all()

def get_menu_by_date(db: Session, date, company_id=None):
    return db.query(DailyMenu).filter(
        DailyMenu.date == date,
        or_(
            DailyMenu.company_id == company_id,
            DailyMenu.company_id.is_(None)
        )
    ).first()


# ---------- EMPLOYEE ----------

def create_food_selection(db: Session, user, data):
    menu = get_menu_by_date(db, data.date, user.company_id)
    if not menu:
        raise HTTPException(404, "Menu not available")

    # Check duplicate per meal
    exists = db.query(FoodSelection).filter_by(
        employee_id=user.id,
        meal_type=data.meal_type,
        date=data.date
    ).first()

    if exists:
        raise HTTPException(400, "Already selected for this meal")

    # Validate food
    food = db.query(FoodItem).filter(FoodItem.id == data.food_item_id).first()

    if not food:
        raise HTTPException(404, "Food not found")

    if food.category != data.meal_type:
        raise HTTPException(400, "Invalid meal type")

    # Check menu availability
    allowed_ids = [item.food_item_id for item in menu.items]
    if data.food_item_id not in allowed_ids:
        raise HTTPException(400, "Food not in menu")

    # Cutoff logic
    now = datetime.now().time()
    cutoff_map = {"BREAKFAST": 8, "LUNCH": 12, "DINNER": 19}

    if now.hour >= cutoff_map[data.meal_type]:
        raise HTTPException(400, f"{data.meal_type} closed")

    selection = FoodSelection(
        employee_id=user.id,
        company_id=user.company_id,
        food_item_id=data.food_item_id,
        meal_type=data.meal_type,
        suggestion=data.suggestion,
        date=data.date
    )

    db.add(selection)
    db.commit()

    return {"message": "Food selected"}


# ---------- COUNT ----------

def get_food_count(db: Session, date):
    result = db.execute(
        text("""
            SELECT fi.category, fi.name, COUNT(fs.id)
            FROM food_selections fs
            JOIN food_items fi ON fi.id = fs.food_item_id
            WHERE fs.date = :date
            GROUP BY fi.category, fi.name
        """),
        {"date": date}
    ).fetchall()

    return [
        {"category": r[0], "food_name": r[1], "count": r[2]}
        for r in result
    ]