from sqlalchemy import Column, Integer, String, ForeignKey, Enum, Boolean, CheckConstraint, Index, text
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

    # 🔐 AUTH FIELDS
    # NOTE: email / mobile / roll_no / google_id uniqueness is enforced by
    # PARTIAL indexes (see __table_args__) so that a soft-deleted user does
    # not permanently squat on their identifiers — a new user with the same
    # email/mobile can be onboarded after the previous one is deleted_at.
    email = Column(String, index=True, nullable=True)
    password_hash = Column(String, nullable=True)

    user_type = Column(Enum(UserTypes, name="user_types_enum"), default=UserTypes.employee, nullable=False, index=True)
    google_id = Column(String, nullable=True, index=True)

    # 👤 EMPLOYEE DETAILS
    name = Column(String(255), nullable=False)
    roll_no = Column(String(50), index=True, nullable=True)
    mobile = Column(String(20), index=True, nullable=True)
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
        # Partial unique indexes: enforce uniqueness only among live
        # (non-soft-deleted) rows so a re-onboard with the same email/mobile/
        # roll_no/google_id is possible after the original is deleted_at.
        Index(
            "uq_employees_email_active",
            "email",
            unique=True,
            postgresql_where=text("deleted_at IS NULL AND email IS NOT NULL"),
        ),
        Index(
            "uq_employees_mobile_active",
            "mobile",
            unique=True,
            postgresql_where=text("deleted_at IS NULL AND mobile IS NOT NULL"),
        ),
        Index(
            "uq_employees_roll_no_active",
            "roll_no",
            unique=True,
            postgresql_where=text("deleted_at IS NULL AND roll_no IS NOT NULL"),
        ),
        Index(
            "uq_employees_google_id_active",
            "google_id",
            unique=True,
            postgresql_where=text("deleted_at IS NULL AND google_id IS NOT NULL"),
        ),

        CheckConstraint(
            "(user_type IN ('staff', 'employee') AND company_id IS NOT NULL) OR "
            "(user_type IN ('super_admin', 'office_admin'))",
            name="check_company_required"
        ),
    )