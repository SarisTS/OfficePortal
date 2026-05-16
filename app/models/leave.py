from sqlalchemy import (Column, Integer, String, ForeignKey, Date, Text,
    Enum, Boolean, Index, DateTime, Float, UniqueConstraint)
from sqlalchemy.orm import relationship
from app.database.base import Base
from app.models.base import AuditMixin
import enum


class LeaveStatus(str, enum.Enum):
    pending = "pending"
    approved = "approved"
    rejected = "rejected"


class LeaveType(str, enum.Enum):
    casual = "casual"
    sick = "sick"
    earned = "earned"


class Leave(Base, AuditMixin):
    __tablename__ = "leaves"

    id = Column(Integer, primary_key=True)

    employee_id = Column(Integer, ForeignKey("employees.id"), nullable=False, index=True)

    leave_type = Column(Enum(LeaveType), nullable=False)

    start_date = Column(Date, nullable=False)
    end_date = Column(Date, nullable=False)

    is_half_day = Column(Boolean, default=False)

    reason = Column(Text)
    contact_number = Column(String(20))

    status = Column(Enum(LeaveStatus), default=LeaveStatus.pending, nullable=False)

    approved_by = Column(Integer, ForeignKey("employees.id"), nullable=True)
    approved_at = Column(DateTime, nullable=True)

    # 🔥 FIXED RELATIONSHIPS

    employee = relationship(
        "Employee",
        foreign_keys=[employee_id],
        back_populates="leaves"
    )

    approver = relationship(
        "Employee",
        foreign_keys=[approved_by]
    )

    __table_args__ = (
        Index("idx_leave_employee_dates", "employee_id", "start_date", "end_date"),
        # Admin dashboards list "pending" leaves all the time; the status
        # column is low-cardinality but frequently filtered.
        Index("idx_leave_status", "status"),
    )


class LeavePolicy(Base, AuditMixin):
    """How many days of each leave_type a company grants per year.

    One row per (company, leave_type). super_admin / office_admin create
    these; the absence of a policy for a given type means employees in
    that company cannot request that type of leave.
    """
    __tablename__ = "leave_policies"

    id = Column(Integer, primary_key=True)

    company_id = Column(Integer, ForeignKey("companies.id"), nullable=False, index=True)

    leave_type = Column(Enum(LeaveType), nullable=False)

    # Float so half-day-precision entitlements ("12.5 days/year") work.
    annual_entitlement = Column(Float, nullable=False)

    company = relationship("Company")

    __table_args__ = (
        UniqueConstraint("company_id", "leave_type", name="uq_leave_policy"),
    )


class LeaveBalance(Base, AuditMixin):
    """Per-employee, per-year, per-leave_type ledger.

    `allocated` is seeded from the matching LeavePolicy when the row is
    first created (lazy on first read / first request). `used` is mutated
    when leaves are approved (debit) or approved leaves are cancelled
    (refund). `remaining = allocated - used` is computed in the schema,
    not stored.

    The (employee_id, year, leave_type) tuple is unique so every
    employee has at most one row per year per type.
    """
    __tablename__ = "leave_balances"

    id = Column(Integer, primary_key=True)

    employee_id = Column(Integer, ForeignKey("employees.id"), nullable=False, index=True)
    year = Column(Integer, nullable=False)
    leave_type = Column(Enum(LeaveType), nullable=False)

    allocated = Column(Float, nullable=False, default=0)
    used = Column(Float, nullable=False, default=0)

    employee = relationship("Employee")

    __table_args__ = (
        UniqueConstraint(
            "employee_id", "year", "leave_type", name="uq_leave_balance"
        ),
        Index(
            "idx_leave_balance_lookup",
            "employee_id", "year", "leave_type",
        ),
    )