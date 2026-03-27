from pydantic import BaseModel, field_validator
from datetime import date
from typing import Optional
from app.models.leave import LeaveType, LeaveStatus


class LeaveCreate(BaseModel):
    employee_id: int
    leave_type: LeaveType

    start_date: date
    end_date: date

    reason: Optional[str] = None
    contact_number: Optional[str] = None

    @field_validator("end_date")
    def validate_dates(cls, v, values):
        start = values.data.get("start_date")
        if start and v < start:
            raise ValueError("end_date must be >= start_date")
        return v
    
class LeaveUpdate(BaseModel):
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

    status: LeaveStatus

    reason: Optional[str] = None
    contact_number: Optional[str] = None

    approved_by: Optional[int] = None
    approved_at: Optional[datetime] = None

    class Config:
        from_attributes = True