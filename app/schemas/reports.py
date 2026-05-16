from typing import Optional

from pydantic import BaseModel, ConfigDict


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
