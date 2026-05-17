from pydantic import BaseModel, ConfigDict, field_validator
from datetime import date
from typing import Optional

from app.models.leave import LeaveType, LeaveStatus
from app.schemas.base import StrictRequestModel


class LeaveCreate(StrictRequestModel):
    employee_id: int
    leave_type: LeaveType

    start_date: date
    end_date: date

    is_half_day: Optional[bool] = False

    reason: Optional[str] = None
    contact_number: Optional[str] = None

    @field_validator("end_date")
    def validate_dates(cls, v, values):
        start = values.data.get("start_date")
        if start and v < start:
            raise ValueError("end_date must be >= start_date")
        return v
    
class LeaveUpdate(StrictRequestModel):
    start_date: Optional[date] = None
    end_date: Optional[date] = None

    reason: Optional[str] = None
    contact_number: Optional[str] = None

from datetime import datetime


class LeaveResponse(BaseModel):
    id: int
    employee_id: int
    leave_type: LeaveType

    start_date: date
    end_date: date

    is_half_day: bool = False

    status: LeaveStatus

    reason: Optional[str] = None
    contact_number: Optional[str] = None

    approved_by: Optional[int] = None
    approved_at: Optional[datetime] = None

    model_config = ConfigDict(from_attributes=True)


# ---------- Leave Policy ----------

class LeavePolicyCreate(StrictRequestModel):
    company_id: int
    leave_type: LeaveType
    annual_entitlement: float

    @field_validator("annual_entitlement")
    def must_be_non_negative(cls, v):
        if v < 0:
            raise ValueError("annual_entitlement must be >= 0")
        return v


class LeavePolicyUpdate(StrictRequestModel):
    annual_entitlement: float

    @field_validator("annual_entitlement")
    def must_be_non_negative(cls, v):
        if v < 0:
            raise ValueError("annual_entitlement must be >= 0")
        return v


class LeavePolicyResponse(BaseModel):
    id: int
    company_id: int
    leave_type: LeaveType
    annual_entitlement: float

    model_config = ConfigDict(from_attributes=True)


# ---------- Leave Balance ----------

class LeaveBalanceResponse(BaseModel):
    """Read-only view. `remaining` is computed from allocated - used."""
    id: int
    employee_id: int
    year: int
    leave_type: LeaveType
    allocated: float
    used: float
    remaining: float

    model_config = ConfigDict(from_attributes=True)


class LeaveBalanceAdjustRequest(StrictRequestModel):
    """Admin-only adjustment with a required reason for audit trail."""
    year: int
    leave_type: LeaveType
    # Signed delta on `allocated`. +5 grants 5 more days, -3 takes 3 back.
    delta: float
    reason: str

    @field_validator("reason")
    def reason_must_be_present(cls, v):
        if not v or not v.strip():
            raise ValueError("reason is required")
        return v.strip()