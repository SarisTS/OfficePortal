from sqlalchemy import Column, Integer, String, Date, ForeignKey, UniqueConstraint, Text, Enum, Index
from sqlalchemy.orm import relationship
from app.database.base import Base


class FoodItem(Base):
    __tablename__ = "food_items"

    id = Column(Integer, primary_key=True)
    name = Column(String(100), nullable=False)
    category = Column(Enum("BREAKFAST", "LUNCH", "DINNER", name="meal_enum"), nullable=False)


class DailyMenu(Base):
    __tablename__ = "daily_menus"

    id = Column(Integer, primary_key=True)
    date = Column(Date, nullable=False)
    company_id = Column(Integer, nullable=True)

    items = relationship("DailyMenuItem", back_populates="menu", cascade="all, delete")


class DailyMenuItem(Base):
    __tablename__ = "daily_menu_items"

    id = Column(Integer, primary_key=True)
    daily_menu_id = Column(Integer, ForeignKey("daily_menus.id", ondelete="CASCADE"))
    food_item_id = Column(Integer, ForeignKey("food_items.id", ondelete="CASCADE"))

    menu = relationship("DailyMenu", back_populates="items")
    food = relationship("FoodItem")


class FoodSelection(Base):
    __tablename__ = "food_selections"

    id = Column(Integer, primary_key=True)
    employee_id = Column(Integer, nullable=False)
    company_id = Column(Integer, nullable=True)
    food_item_id = Column(Integer, ForeignKey("food_items.id", ondelete="CASCADE"))

    meal_type = Column(Enum("BREAKFAST", "LUNCH", "DINNER", name="meal_enum"), nullable=False)

    suggestion = Column(Text, nullable=True)
    date = Column(Date, nullable=False)

    __table_args__ = (
        UniqueConstraint("employee_id", "meal_type", "date", name="unique_meal_selection"),
        Index("idx_food_selection_date", "date"),
        Index("idx_food_employee_date", "employee_id", "date"),
    )