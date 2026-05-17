from pydantic import BaseModel, ConfigDict, EmailStr
from typing import Optional
from datetime import datetime

from app.models.employee import UserTypes
from app.schemas.base import StrictRequestModel


class EmployeeCreate(StrictRequestModel):
    name: str
    email: EmailStr
    company_id: int
    role_id: int
    user_type: UserTypes
    department_id: Optional[int] = None
    hostel_id: Optional[int] = None
    mobile: Optional[str] = None
    address_line_1 : Optional[str] = None
    address_line_2 : Optional[str] = None
    landmark : Optional[str] = None
    city : Optional[str] = None
    state : Optional[str] = None
    pincode : Optional[str] = None


class EmployeeUpdate(StrictRequestModel):
    roll_no: Optional[str] = None
    name: str
    email: EmailStr
    role_id: int
    user_type: UserTypes
    department_id: Optional[int] = None
    hostel_id: Optional[int] = None
    mobile: Optional[str] = None
    address_line_1 : Optional[str] = None
    address_line_2 : Optional[str] = None
    landmark : Optional[str] = None
    city : Optional[str] = None
    state : Optional[str] = None
    pincode : Optional[str] = None


class ProfileUpdate(StrictRequestModel):
    """Self-service profile edit — narrow allowlist of fields an employee
    is permitted to change about themselves. Anything not listed here
    (name, roll_no, role_id, user_type, company/department/hostel,
    is_verified, is_active) is admin-only and goes through PUT
    /employees/{id}.

    StrictRequestModel's extra="forbid" makes unknown fields a 422 at
    parse time, so attempts to smuggle e.g. user_type are rejected
    before the handler sees them.
    """
    mobile: Optional[str] = None
    email: Optional[EmailStr] = None
    address_line_1: Optional[str] = None
    address_line_2: Optional[str] = None
    landmark: Optional[str] = None
    city: Optional[str] = None
    state: Optional[str] = None
    pincode: Optional[str] = None


class EmployeeResponse(BaseModel):
    id: int
    roll_no: Optional[str] = None
    name: str
    email: Optional[EmailStr] = None
    user_type: UserTypes

    role_id: int
    role_name: Optional[str] = None

    company_id: Optional[int] = None
    department_id: Optional[int] = None
    department_name: Optional[str] = None

    hostel_id: Optional[int] = None

    mobile: Optional[str] = None

    address_line_1: Optional[str] = None
    address_line_2: Optional[str] = None
    landmark: Optional[str] = None
    city: Optional[str] = None
    state: Optional[str] = None
    pincode: Optional[str] = None

    is_active: Optional[bool] = True

    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)


class EmployeeBulkImportResult(BaseModel):
    """Response shape for POST /employees/import — mirrors the bulk
    patterns used by holiday and payslip generation: a list of created
    rows plus a `skipped` list whose entries carry the row number and
    per-row error details so the admin can fix and re-upload."""
    created: list[EmployeeResponse]
    skipped: list[dict]
