"""Company non-working-day calendar.

Two tables, both consulted by leave-day counting and payroll LWP
exclusion:

  CompanyHoliday      explicit date-based holidays
                      (Republic Day, Diwali, etc.)

  CompanyWeeklyOff    recurring weekly non-working days
                      (e.g. every Sunday — day_of_week=6)

The union of these for a given period is computed by
crud.holiday.non_working_dates_in_range, which is what the leave and
payroll services consult.
"""
from sqlalchemy import (
    CheckConstraint, Column, Date, ForeignKey, Index, Integer, String,
    UniqueConstraint,
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


class CompanyWeeklyOff(Base, AuditMixin):
    """Recurring weekly non-working day for a company.

    `day_of_week` follows Python's `date.weekday()`:
        0 = Monday, 1 = Tuesday, ..., 6 = Sunday.

    One row per (company_id, day_of_week). To mark BOTH Saturday AND
    Sunday off, the admin creates two rows. There's no "alternate
    Saturday" support — that's a different abstraction (date-based or
    week-number-based) that can land separately if needed.
    """
    __tablename__ = "company_weekly_offs"

    id = Column(Integer, primary_key=True)
    company_id = Column(
        Integer, ForeignKey("companies.id"), nullable=False, index=True
    )
    day_of_week = Column(Integer, nullable=False)

    company = relationship("Company")

    __table_args__ = (
        UniqueConstraint(
            "company_id", "day_of_week", name="uq_company_weekly_off"
        ),
        CheckConstraint(
            "day_of_week >= 0 AND day_of_week <= 6",
            name="check_weekly_off_day_of_week",
        ),
    )
