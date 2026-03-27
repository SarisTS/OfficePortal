from sqlalchemy import Column, Integer, Date, ForeignKey, String, DateTime, UniqueConstraint, Index, Float, Boolean
from sqlalchemy.orm import relationship
from app.database.base import Base
from app.models.base import AuditMixin


class EmployeeCompanyAssignment(Base, AuditMixin):
    __tablename__ = "employee_company_assignments"

    id = Column(Integer, primary_key=True)

    employee_id = Column(Integer, ForeignKey("employees.id"), nullable=False)

    company_id = Column(Integer, ForeignKey("companies.id"), nullable=False)

    start_date = Column(Date, nullable=False)

    end_date = Column(Date, nullable=True)

    employee = relationship("Employee", back_populates="company_assignments")

    company = relationship("Company")


class EmployeeShiftAssignment(Base, AuditMixin):
    __tablename__ = "employee_shift_assignments"

    id = Column(Integer, primary_key=True)

    employee_id = Column(Integer, ForeignKey("employees.id"), nullable=False)

    shift_id = Column(Integer, ForeignKey("shifts.id"), nullable=False)

    start_date = Column(Date, nullable=False)

    end_date = Column(Date, nullable=True)

    employee = relationship("Employee", back_populates="shift_assignments")

    shift = relationship("Shift", back_populates="assignments")

    __table_args__ = (
        UniqueConstraint("employee_id", "end_date", name="unique_active_shift"),
        Index("idx_employee_shift", "employee_id", "start_date")
    )

class EmployeeDeviceLog(Base, AuditMixin):
    __tablename__ = "employee_device_logs"

    id = Column(Integer, primary_key=True)

    employee_id = Column(Integer, ForeignKey("employees.id"), nullable=False)

    ip_address = Column(String(50))

    device_info = Column(String(255))

    login_time = Column(DateTime)

    logout_time = Column(DateTime)

    employee = relationship("Employee")

class CompanyLocation(Base, AuditMixin):
    __tablename__ = "company_locations"

    id = Column(Integer, primary_key=True)

    name = Column(String(100), nullable=False)

    latitude = Column(Float, nullable=False)
    longitude = Column(Float, nullable=False)

    radius = Column(Integer, default=100)  # meters

    is_primary = Column(Boolean, default=False)  # 🔥 useful

    company_id = Column(Integer, ForeignKey("companies.id"), nullable=False)

    company = relationship("Company", back_populates="locations")

    __table_args__ = (
        Index("idx_company_location", "company_id"),
    )