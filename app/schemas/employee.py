from pydantic import BaseModel, EmailStr
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

    class Config:
        from_attributes = True
