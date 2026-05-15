from sqlalchemy import Column, Integer, String, Date, ForeignKey, UniqueConstraint, Text, Enum, Index
from sqlalchemy.orm import relationship
from app.database.base import Base
from app.models.base import AuditMixin


class FoodItem(Base, AuditMixin):
    __tablename__ = "food_items"

    id = Column(Integer, primary_key=True)
    name = Column(String(100), nullable=False)
    category = Column(Enum("BREAKFAST", "LUNCH", "DINNER", name="meal_enum"), nullable=False)


class DailyMenu(Base, AuditMixin):
    __tablename__ = "daily_menus"

    id = Column(Integer, primary_key=True)
    date = Column(Date, nullable=False)
    company_id = Column(Integer, ForeignKey("companies.id"), nullable=True)

    items = relationship("DailyMenuItem", back_populates="menu", cascade="all, delete")

    __table_args__ = (
        # One menu per company per day. Pre-existing duplicates must be
        # collapsed before the matching migration can apply.
        UniqueConstraint("company_id", "date", name="uq_daily_menu_company_date"),
        Index("idx_daily_menu_company_date", "company_id", "date"),
    )


class DailyMenuItem(Base, AuditMixin):
    __tablename__ = "daily_menu_items"

    id = Column(Integer, primary_key=True)
    daily_menu_id = Column(Integer, ForeignKey("daily_menus.id", ondelete="CASCADE"))
    food_item_id = Column(Integer, ForeignKey("food_items.id", ondelete="CASCADE"))

    menu = relationship("DailyMenu", back_populates="items")
    food = relationship("FoodItem")

    __table_args__ = (
        UniqueConstraint("daily_menu_id", "food_item_id", name="uq_menu_item"),
    )


class FoodSelection(Base, AuditMixin):
    __tablename__ = "food_selections"

    id = Column(Integer, primary_key=True)
    employee_id = Column(Integer, ForeignKey("employees.id"), nullable=False)
    company_id = Column(Integer, ForeignKey("companies.id"), nullable=True)
    food_item_id = Column(Integer, ForeignKey("food_items.id", ondelete="CASCADE"))

    meal_type = Column(Enum("BREAKFAST", "LUNCH", "DINNER", name="meal_enum"), nullable=False)

    suggestion = Column(Text, nullable=True)
    date = Column(Date, nullable=False)

    __table_args__ = (
        UniqueConstraint("employee_id", "meal_type", "date", name="unique_meal_selection"),
        Index("idx_food_selection_date", "date"),
        Index("idx_food_employee_date", "employee_id", "date"),
    )
