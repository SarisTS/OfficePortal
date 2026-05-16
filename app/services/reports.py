"""Aggregated report queries.

Replaces the old monthly_report_service.py — that module computed
counts in Python by `sum(1 for r in records if ...)`, used a hardcoded
day=31 end_date (crashes for Feb/Apr/etc), did string-vs-enum status
comparisons that always returned False, and never filtered out
soft-deleted rows. All of that is fixed here by pushing the COUNT
/ SUM into the DB with a `CASE WHEN` per status (portable across
Postgres and SQLite — `FILTER` is PG-only).
"""
from __future__ import annotations

from calendar import monthrange
from datetime import date

from fastapi import HTTPException
from sqlalchemy import case, func, select
from sqlalchemy.orm import Session

from app.models.attendance import Attendance, AttendanceStatus
from app.models.employee import Employee


def _month_range(year: int, month: int) -> tuple[date, date]:
    """Return (first, last) day of the month. monthrange() gives the
    actual last day so Feb-29 / Apr-30 etc. all work."""
    if not 1 <= month <= 12:
        raise HTTPException(400, "month must be in 1..12")
    _, last = monthrange(year, month)
    return date(year, month, 1), date(year, month, last)


def _count_status(status: AttendanceStatus):
    """`SUM(CASE WHEN attendance_status = :s THEN 1 ELSE 0 END)` —
    portable replacement for PG's `COUNT(*) FILTER (WHERE ...)`."""
    return func.sum(
        case((Attendance.attendance_status == status, 1), else_=0)
    )


def _row_to_dict(row, year: int, month: int) -> dict:
    """Coerce a SQLAlchemy Row into the schema-friendly dict shape.
    Handles NULL → 0 / 0.0 for the SUM columns."""
    return {
        "employee_id": row.employee_id,
        "employee_name": row.employee_name,
        "year": year,
        "month": month,
        "days_present": int(row.days_present or 0),
        "days_absent": int(row.days_absent or 0),
        "days_half_day": int(row.days_half_day or 0),
        "days_late": int(row.days_late or 0),
        "days_on_leave": int(row.days_on_leave or 0),
        "total_working_hours": float(row.total_working_hours or 0),
        "total_late_minutes": int(row.total_late_minutes or 0),
    }


def _base_summary_query(year: int, month: int):
    """The select() shape both endpoints reuse — group + counters but
    no scope filter. Caller adds the company_id / employee_id WHERE."""
    start_date, end_date = _month_range(year, month)
    return (
        select(
            Attendance.employee_id.label("employee_id"),
            Employee.name.label("employee_name"),
            _count_status(AttendanceStatus.present).label("days_present"),
            _count_status(AttendanceStatus.absent).label("days_absent"),
            _count_status(AttendanceStatus.half_day).label("days_half_day"),
            _count_status(AttendanceStatus.late).label("days_late"),
            _count_status(AttendanceStatus.leave).label("days_on_leave"),
            func.coalesce(func.sum(Attendance.working_hours), 0)
            .label("total_working_hours"),
            func.coalesce(func.sum(Attendance.late_minutes), 0)
            .label("total_late_minutes"),
        )
        .select_from(Attendance)
        .join(Employee, Employee.id == Attendance.employee_id)
        .where(
            Attendance.deleted_at.is_(None),
            Attendance.date >= start_date,
            Attendance.date <= end_date,
        )
        .group_by(Attendance.employee_id, Employee.name)
        .order_by(Employee.name)
    )


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

def attendance_summary_for_company(
    db: Session, company_id: int, year: int, month: int
) -> list[dict]:
    """One row per employee in the company who has at least one
    attendance record in the period. Employees with zero records simply
    don't appear (callers can join against the employee roster if they
    want zero-padded rows)."""
    stmt = _base_summary_query(year, month).where(
        Attendance.company_id == company_id
    )
    return [_row_to_dict(r, year, month) for r in db.execute(stmt).all()]


def attendance_summary_for_employee(
    db: Session, employee_id: int, year: int, month: int
) -> dict:
    """Single-employee version. Returns zeros (not 404) when the employee
    has no rows in the period — reports should show '0 days', not
    surface as an error."""
    stmt = _base_summary_query(year, month).where(
        Attendance.employee_id == employee_id
    )
    row = db.execute(stmt).first()
    if row is not None:
        return _row_to_dict(row, year, month)

    # No attendance for this period — return a zero row tagged with the
    # employee's name (if they exist) so the frontend still has a header.
    employee = (
        db.query(Employee)
        .filter(Employee.id == employee_id, Employee.deleted_at.is_(None))
        .first()
    )
    return {
        "employee_id": employee_id,
        "employee_name": employee.name if employee else None,
        "year": year,
        "month": month,
        "days_present": 0,
        "days_absent": 0,
        "days_half_day": 0,
        "days_late": 0,
        "days_on_leave": 0,
        "total_working_hours": 0.0,
        "total_late_minutes": 0,
    }
