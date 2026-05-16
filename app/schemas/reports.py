from typing import Optional

from pydantic import BaseModel, ConfigDict

from app.models.leave import LeaveType


class AttendanceMonthlySummary(BaseModel):
    """One row per (employee, year, month). All `days_*` counts come
    from a SQL-side `SUM(CASE WHEN ...)` aggregation; hours/minutes are
    `SUM(...)` over the period."""

    employee_id: int
    employee_name: Optional[str] = None

    year: int
    month: int

    days_present: int
    days_absent: int
    days_half_day: int
    days_late: int
    days_on_leave: int

    total_working_hours: float
    total_late_minutes: int

    model_config = ConfigDict(from_attributes=True)


class LeaveUsageRow(BaseModel):
    """One row per leave_type in the leave usage report."""
    leave_type: LeaveType
    total_allocated: float
    total_used: float
    total_remaining: float
    pending_requests: int

    model_config = ConfigDict(from_attributes=True)


class PayrollMonthlyTotal(BaseModel):
    """Aggregated totals across every payslip in a (company, year, month)."""
    company_id: int
    year: int
    month: int
    payslip_count: int
    total_gross: float
    total_deductions: float
    total_net: float
    # Mean of `net` across the payslips. 0 when payslip_count == 0
    # (avoids NaN that would come from SQL AVG over an empty group).
    average_net: float

    model_config = ConfigDict(from_attributes=True)
