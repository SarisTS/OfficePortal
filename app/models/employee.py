from sqlalchemy import Column, Integer, String, ForeignKey, Enum, Boolean, CheckConstraint, Index
from sqlalchemy.orm import relationship
from app.database.base import Base
from app.models.base import AuditMixin
import enum


class UserTypes(str, enum.Enum):
    super_admin = "super_admin"
    office_admin = "office_admin"
    staff = "staff"
    employee = "employee"


class Employee(Base, AuditMixin):
    __tablename__ = "employees"

    id = Column(Integer, primary_key=True)

    # 🔐 AUTH FIELDS (moved from User)
    email = Column(String, unique=True, index=True, nullable=True)
    password_hash = Column(String, nullable=True)

    user_type = Column(Enum(UserTypes, name="user_types_enum"), default=UserTypes.employee, nullable=False, index=True)
    google_id = Column(String, unique=True, nullable=True, index=True)

    # 👤 EMPLOYEE DETAILS
    name = Column(String(255), nullable=False)
    roll_no = Column(String(50), unique=True, index=True, nullable=True)
    mobile = Column(String(20), unique=True, index=True, nullable=True)
    is_verified = Column(Boolean, default=False)

    address_line_1 = Column(String(255), nullable=True)
    address_line_2 = Column(String(255), nullable=True)
    landmark = Column(String(255), nullable=True)

    city = Column(String(100), nullable=True)
    state = Column(String(100), nullable=True)
    pincode = Column(String(20), nullable=True)

    # 🏢 ORGANIZATION
    company_id = Column(Integer, ForeignKey("companies.id"), nullable=True, index=True)
    department_id = Column(Integer, ForeignKey("departments.id"), nullable=True, index=True)
    hostel_id = Column(Integer, ForeignKey("hostels.id"), nullable=True, index=True)

    role_id = Column(Integer, ForeignKey("roles.id"), nullable=False, index=True)

    # 🔗 RELATIONSHIPS
    role = relationship("Role", back_populates="employees", lazy="selectin")

    company = relationship("Company", back_populates="employees")
    department = relationship("Department")
    hostel = relationship("Hostel", back_populates="employees")

    shift_assignments = relationship("EmployeeShiftAssignment", back_populates="employee")
    company_assignments = relationship("EmployeeCompanyAssignment", back_populates="employee")

    attendance = relationship("Attendance", back_populates="employee")
    leaves = relationship("Leave", back_populates="employee", foreign_keys="Leave.employee_id")

    __table_args__ = (
        Index("idx_employee_email", "email"),
        Index("idx_employee_mobile", "mobile"),
        Index("idx_employee_roll", "roll_no"),

        CheckConstraint(
            "(user_type IN ('staff', 'employee') AND company_id IS NOT NULL) OR "
            "(user_type IN ('super_admin', 'office_admin'))",
            name="check_company_required"
        ),
    )