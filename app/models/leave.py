from sqlalchemy import Column, Integer, String, ForeignKey, Date, Text, Enum, Boolean, Index, DateTime
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