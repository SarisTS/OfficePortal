from sqlalchemy import (Column, Integer, ForeignKey, Date, DateTime, Float,
    Enum, String, Time, Index, UniqueConstraint, Boolean)
from sqlalchemy.orm import relationship
import enum

from app.database.base import Base
from app.models.base import AuditMixin


class AttendanceStatus(str, enum.Enum):
    present = "present"
    absent = "absent"
    half_day = "half_day"
    late = "late"
    leave = "leave"


class Attendance(Base, AuditMixin):
    __tablename__ = "attendance"

    id = Column(Integer, primary_key=True)

    employee_id = Column(Integer, ForeignKey("employees.id"), nullable=False)
    company_id = Column(Integer, ForeignKey("companies.id"), nullable=False)

    shift_id = Column(Integer, ForeignKey("shifts.id"), nullable=True)

    date = Column(Date, nullable=False)

    check_in = Column(DateTime(timezone=True))
    check_out = Column(DateTime(timezone=True))

    check_in_lat = Column(Float)
    check_in_lon = Column(Float)

    check_out_lat = Column(Float)
    check_out_lon = Column(Float)

    company_location_id = Column(Integer, ForeignKey("company_locations.id"))

    working_hours = Column(Float)
    late_minutes = Column(Integer, default=0)

    attendance_status = Column(Enum(AttendanceStatus), default=AttendanceStatus.present)

    source = Column(String, default="mobile")

    is_manual = Column(Boolean, default=False)
    manual_reason = Column(String)

    employee = relationship("Employee")
    shift = relationship("Shift")
    company_location = relationship("CompanyLocation")

    __table_args__ = (
        UniqueConstraint("employee_id", "date", name="unique_employee_attendance"),
        Index("idx_employee_date", "employee_id", "date"),
    )

class Shift(Base, AuditMixin):
    __tablename__ = "shifts"

    id = Column(Integer, primary_key=True)

    name = Column(String, nullable=False)

    start_time = Column(Time, nullable=False)

    end_time = Column(Time, nullable=False)

    grace_minutes = Column(Integer, default=10)

    company_id = Column(Integer, ForeignKey("companies.id"))
    company = relationship("Company")
    assignments = relationship("EmployeeShiftAssignment", back_populates="shift")




