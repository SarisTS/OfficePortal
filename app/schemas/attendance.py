from pydantic import BaseModel, Field, field_validator
from datetime import date, datetime
from typing import Optional

from app.models.attendance import AttendanceStatus
from app.schemas.base import StrictRequestModel


# Reusable WGS84 lat/lon bounds.
Latitude = Field(..., ge=-90, le=90)
Longitude = Field(..., ge=-180, le=180)


class AttendanceBase(StrictRequestModel):
    shift_id: int
    date: date


class AttendanceCreate(AttendanceBase):
    employee_id: int
    check_in: Optional[datetime] = None
    check_out: Optional[datetime] = None
    lat: float = Latitude
    lon: float = Longitude

    @field_validator("check_out")
    def validate_checkout(cls, v, values):
        check_in = values.data.get("check_in")
        if v and check_in and v < check_in:
            raise ValueError("check_out cannot be before check_in")
        return v


class AttendanceUpdate(StrictRequestModel):
    check_in: Optional[datetime] = None
    check_out: Optional[datetime] = None
    attendance_status: Optional[AttendanceStatus] = None

    @field_validator("check_out")
    def validate_checkout(cls, v, values):
        check_in = values.data.get("check_in")
        if v and check_in and v < check_in:
            raise ValueError("Invalid checkout time")
        return v


class ManualAttendanceCreate(StrictRequestModel):
    check_in: Optional[datetime] = None
    check_out: Optional[datetime] = None
    reason: Optional[str] = None


class AttendanceResponse(BaseModel):
    id: int

    employee_id: int
    employee_name: Optional[str] = None

    shift_id: Optional[int]
    shift_name: Optional[str] = None

    date: date

    check_in: Optional[datetime]
    check_out: Optional[datetime]

    working_hours: Optional[float]
    late_minutes: int

    attendance_status: AttendanceStatus

    is_manual: Optional[bool] = False
    manual_reason: Optional[str] = None

    class Config:
        from_attributes = True


class AttendanceListResponse(BaseModel):
    total: int
    items: list[AttendanceResponse]


class CheckInRequest(StrictRequestModel):
    lat: float = Latitude
    lon: float = Longitude


class CheckOutRequest(StrictRequestModel):
    lat: float = Latitude
    lon: float = Longitude
