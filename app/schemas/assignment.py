from pydantic import BaseModel
from datetime import date, time
from typing import Optional


class ShiftCreate(BaseModel):
    name: str
    start_time: time
    end_time: time
    grace_minutes: int
    company_id: int

    class Config:
        from_attributes = True


class ShiftUpdate(BaseModel):
    name: str | None = None
    start_time: time | None = None
    end_time: time | None = None
    grace_minutes: int | None = None
    company_id: int


class ShiftResponse(BaseModel):
    id: int
    name: str
    start_time: time
    end_time: time
    grace_minutes: int
    company_id: int

    class Config:
        from_attributes = True


class ShiftAssignmentCreate(BaseModel):
    employee_id: int
    shift_id: int
    start_date: date


class ShiftChangeRequest(BaseModel):
    employee_id: int
    shift_id: int
    start_date: date


class ShiftAssignmentResponse(BaseModel):
    id: int
    employee_id: int
    shift_id: int
    start_date: date
    end_date: Optional[date]

    shift_name: Optional[str] = None

    class Config:
        from_attributes = True