"""Payroll domain — SalaryStructure (effective-dated) + Payslip (snapshot)."""

from datetime import datetime, timezone

from sqlalchemy import (
    Column, Integer, Float, Date, DateTime, ForeignKey, Index,
    UniqueConstraint, CheckConstraint,
)
from sqlalchemy.orm import relationship

from app.database.base import Base
from app.models.base import AuditMixin


class SalaryStructure(Base, AuditMixin):
    """Effective-dated salary blueprint per employee.

    Multiple rows allowed per employee. The "active" structure for a
    given date is the row with the largest effective_from that's not in
    the future. Append-only history — when an employee's salary changes,
    create a new row instead of mutating an existing one, so previously
    generated payslips still tie back to the inputs they used.

    Amounts are stored in the deployment's single currency (INR per
    project convention — see also IST timezone default, mobile-OTP login,
    PF/TDS terminology below).
    """
    __tablename__ = "salary_structures"

    id = Column(Integer, primary_key=True)
    employee_id = Column(
        Integer, ForeignKey("employees.id"), nullable=False, index=True
    )

    # Inclusive — the structure applies from this date onward (until
    # superseded by another row with a later effective_from).
    effective_from = Column(Date, nullable=False)

    # Earnings
    basic = Column(Float, nullable=False, server_default="0")
    hra = Column(Float, nullable=False, server_default="0")
    special_allowance = Column(Float, nullable=False, server_default="0")
    other_allowances = Column(Float, nullable=False, server_default="0")

    # Statutory + ad-hoc deductions. These are flat amounts for MVP;
    # automatic computation from tax slabs is a follow-up.
    pf = Column(Float, nullable=False, server_default="0")
    professional_tax = Column(Float, nullable=False, server_default="0")
    tds = Column(Float, nullable=False, server_default="0")
    other_deductions = Column(Float, nullable=False, server_default="0")

    employee = relationship("Employee")

    __table_args__ = (
        UniqueConstraint(
            "employee_id", "effective_from", name="uq_salary_structure"
        ),
        Index(
            "idx_salary_structure_lookup",
            "employee_id", "effective_from",
        ),
        # DB-level sanity check that no amount goes negative.
        CheckConstraint(
            "basic >= 0 AND hra >= 0 AND special_allowance >= 0 AND "
            "other_allowances >= 0 AND pf >= 0 AND professional_tax >= 0 "
            "AND tds >= 0 AND other_deductions >= 0",
            name="check_salary_structure_non_negative",
        ),
    )


class Payslip(Base, AuditMixin):
    """Snapshotted payslip for (employee, year, month).

    Generated from whichever SalaryStructure was active at the end of
    the month, with all component amounts copied onto this row. Once a
    payslip exists, its values never change — even if the underlying
    SalaryStructure is later edited, past payslips remain immutable
    accounting records.
    """
    __tablename__ = "payslips"

    id = Column(Integer, primary_key=True)
    employee_id = Column(
        Integer, ForeignKey("employees.id"), nullable=False, index=True
    )

    year = Column(Integer, nullable=False)
    month = Column(Integer, nullable=False)  # 1..12

    # Snapshotted earnings
    basic = Column(Float, nullable=False, server_default="0")
    hra = Column(Float, nullable=False, server_default="0")
    special_allowance = Column(Float, nullable=False, server_default="0")
    other_allowances = Column(Float, nullable=False, server_default="0")

    # Snapshotted deductions
    pf = Column(Float, nullable=False, server_default="0")
    professional_tax = Column(Float, nullable=False, server_default="0")
    tds = Column(Float, nullable=False, server_default="0")
    other_deductions = Column(Float, nullable=False, server_default="0")

    # Computed at generation time. Also snapshotted so reads don't have
    # to recompute (and so historical payslips don't drift if rounding
    # rules ever change).
    gross = Column(Float, nullable=False, server_default="0")
    total_deductions = Column(Float, nullable=False, server_default="0")
    net = Column(Float, nullable=False, server_default="0")

    # Informational attendance numbers — populated by generation. For
    # MVP, days_worked == days_in_period and days_lwp == 0 (no
    # pro-rating). When the attendance integration lands, it'll flow
    # in here without a schema migration.
    days_in_period = Column(Integer, nullable=False, server_default="0")
    days_worked = Column(Float, nullable=False, server_default="0")
    days_lwp = Column(Float, nullable=False, server_default="0")

    generated_at = Column(
        DateTime(timezone=True), nullable=False,
        default=lambda: datetime.now(timezone.utc),
    )

    employee = relationship("Employee")

    __table_args__ = (
        UniqueConstraint(
            "employee_id", "year", "month", name="uq_payslip_period"
        ),
        Index("idx_payslip_lookup", "employee_id", "year", "month"),
        CheckConstraint(
            "month >= 1 AND month <= 12",
            name="check_payslip_month_range",
        ),
    )
