"""Company holiday calendar.

One row per (company, date). The calendar is consulted by:
  - app/services/leave_balance.py:compute_leave_days  — a holiday inside
    a requested leave range doesn't count against the balance.
  - app/services/payroll.py:_count_absent_days        — an absent day
    that falls on a holiday isn't LWP (employee shouldn't lose pay for
    a company holiday).

No weekly-off pattern support today — admins enumerate dates. A weekly
schedule abstraction is a separate follow-up if needed.
"""
from sqlalchemy import (
    Column, Date, ForeignKey, Index, Integer, String, UniqueConstraint,
)
from sqlalchemy.orm import relationship

from app.database.base import Base
from app.models.base import AuditMixin


class CompanyHoliday(Base, AuditMixin):
    __tablename__ = "company_holidays"

    id = Column(Integer, primary_key=True)
    company_id = Column(
        Integer, ForeignKey("companies.id"), nullable=False, index=True
    )
    date = Column(Date, nullable=False)
    # Display label — "Republic Day", "Diwali", etc. Required so the
    # /me/holidays response is meaningful to the frontend.
    name = Column(String(255), nullable=False)

    company = relationship("Company")

    __table_args__ = (
        UniqueConstraint("company_id", "date", name="uq_company_holiday"),
        Index("idx_company_holiday_lookup", "company_id", "date"),
    )
