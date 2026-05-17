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
from app.models.leave import Leave, LeaveBalance, LeaveStatus, LeaveType
from app.models.payslip import Payslip


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


def leave_usage_for_company(
    db: Session, company_id: int, year: int
) -> list[dict]:
    """Per-leave-type usage rollup for one (company, year).

    Combines two aggregations:
      1. SUM(allocated) + SUM(used) across all LeaveBalance rows for
         the year, joined to Employee for the company filter.
      2. COUNT(*) of pending Leave rows that START in this year
         (cross-year leaves debit start-year's ledger per the design
         decision in the leave-balance commit).

    Returns one row per leave_type that has either a balance row or a
    pending request in the period. `total_remaining` is derived
    (allocated − used) in the service so the schema doesn't have to.
    """
    bal_stmt = (
        select(
            LeaveBalance.leave_type.label("leave_type"),
            func.coalesce(func.sum(LeaveBalance.allocated), 0)
            .label("total_allocated"),
            func.coalesce(func.sum(LeaveBalance.used), 0)
            .label("total_used"),
        )
        .select_from(LeaveBalance)
        .join(Employee, Employee.id == LeaveBalance.employee_id)
        .where(
            LeaveBalance.year == year,
            LeaveBalance.deleted_at.is_(None),
            Employee.company_id == company_id,
            Employee.deleted_at.is_(None),
        )
        .group_by(LeaveBalance.leave_type)
    )
    bal_rows = {r.leave_type: r for r in db.execute(bal_stmt).all()}

    # Pending leaves whose start_date falls in `year`. Using date-range
    # comparison instead of EXTRACT/strftime keeps the query portable
    # across PG and SQLite.
    pending_stmt = (
        select(
            Leave.leave_type.label("leave_type"),
            func.count().label("pending"),
        )
        .select_from(Leave)
        .join(Employee, Employee.id == Leave.employee_id)
        .where(
            Leave.status == LeaveStatus.pending,
            Leave.deleted_at.is_(None),
            Employee.company_id == company_id,
            Employee.deleted_at.is_(None),
            Leave.start_date >= date(year, 1, 1),
            Leave.start_date <= date(year, 12, 31),
        )
        .group_by(Leave.leave_type)
    )
    pending_rows = {
        r.leave_type: int(r.pending or 0)
        for r in db.execute(pending_stmt).all()
    }

    types = set(bal_rows.keys()) | set(pending_rows.keys())
    result = []
    for lt in sorted(types, key=lambda t: t.value):
        bal = bal_rows.get(lt)
        total_alloc = float(bal.total_allocated or 0) if bal else 0.0
        total_used = float(bal.total_used or 0) if bal else 0.0
        result.append({
            "leave_type": lt,
            "total_allocated": total_alloc,
            "total_used": total_used,
            "total_remaining": total_alloc - total_used,
            "pending_requests": pending_rows.get(lt, 0),
        })
    return result


def payroll_totals_for_company(
    db: Session, company_id: int, year: int, month: int
) -> dict:
    """Aggregated payroll totals for one (company, year, month).

    Sums gross, total_deductions, and net across every payslip in the
    period. Joins Employee for the company filter (Payslip has no
    direct company_id — the link is via the employee). Soft-deleted
    payslips and employees are excluded.

    `average_net` is computed in Python from total_net / payslip_count
    rather than via SQL AVG so the empty-period case (count=0) doesn't
    return NaN / NULL.
    """
    stmt = (
        select(
            func.count().label("payslip_count"),
            func.coalesce(func.sum(Payslip.gross), 0).label("total_gross"),
            func.coalesce(func.sum(Payslip.total_deductions), 0)
            .label("total_deductions"),
            func.coalesce(func.sum(Payslip.net), 0).label("total_net"),
        )
        .select_from(Payslip)
        .join(Employee, Employee.id == Payslip.employee_id)
        .where(
            Payslip.year == year,
            Payslip.month == month,
            Payslip.deleted_at.is_(None),
            Employee.company_id == company_id,
            Employee.deleted_at.is_(None),
        )
    )
    row = db.execute(stmt).first()
    count = int(row.payslip_count or 0)
    total_net = float(row.total_net or 0)
    return {
        "company_id": company_id,
        "year": year,
        "month": month,
        "payslip_count": count,
        "total_gross": float(row.total_gross or 0),
        "total_deductions": float(row.total_deductions or 0),
        "total_net": total_net,
        "average_net": (total_net / count) if count > 0 else 0.0,
    }


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
