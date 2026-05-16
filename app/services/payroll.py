"""Payslip generation.

Snapshots the SalaryStructure active on the last day of the (year,
month) into a new Payslip row. Refuses if a payslip already exists for
that period (no implicit "regenerate" — delete the existing one
first). Refuses if no SalaryStructure applies.

MVP scope:
  - no attendance-based pro-rating; days_worked = days_in_period
  - no per-row tax slab computation; deductions are flat amounts copied
    from the structure
"""
from __future__ import annotations

from calendar import monthrange
from datetime import date, datetime, timezone

from fastapi import HTTPException
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.crud.salary_structure import get_current_structure
from app.models.attendance import Attendance, AttendanceStatus
from app.models.employee import Employee, UserTypes
from app.models.payslip import Payslip
from app.services.audit import log_audit, snapshot


def _last_day_of_month(year: int, month: int) -> date:
    _, days = monthrange(year, month)
    return date(year, month, days)


def _count_absent_days(
    db: Session, employee_id: int, company_id: int | None,
    year: int, month: int,
) -> int:
    """Return how many days in the (year, month) the employee was marked
    `absent` in the attendance ledger, EXCLUDING days that are company
    holidays.

    Other AttendanceStatus values — present / late / half_day / leave —
    all count as worked time:

      - present / late: clocked in
      - half_day:       worked the half (first-cut simplification; a
                        follow-up could count as 0.5 worked days)
      - leave:          approved leave (currently casual/sick/earned
                        are ALL paid leave types — none are "loss of
                        pay"). Adding an unpaid leave_type later would
                        need its days counted here too.

    Only `absent` is "loss of pay" today. And even an `absent` row on
    a company-declared holiday isn't LWP — the employee shouldn't lose
    pay for a holiday they couldn't attend on anyway.

    `company_id=None` defends against the edge case where the employee
    isn't bound to any company; in that case there's no holiday calendar
    to consult so all absent rows count as LWP.
    """
    # Import lazily so payroll.py doesn't pull crud/holiday at import.
    # non_working_dates_in_range unions explicit holidays + weekly-off
    # pattern, so absence on a Sunday (when the company declares Sunday
    # as a weekly off) doesn't reduce pay.
    from app.crud.holiday import non_working_dates_in_range

    _, last = monthrange(year, month)
    start_date = date(year, month, 1)
    end_date = date(year, month, last)

    stmt = select(func.count(Attendance.id)).where(
        Attendance.employee_id == employee_id,
        Attendance.attendance_status == AttendanceStatus.absent,
        Attendance.deleted_at.is_(None),
        Attendance.date >= start_date,
        Attendance.date <= end_date,
    )

    if company_id is not None:
        non_working = non_working_dates_in_range(
            db, company_id, start_date, end_date
        )
        if non_working:
            stmt = stmt.where(Attendance.date.notin_(non_working))

    return int(db.execute(stmt).scalar() or 0)


def generate_payslip(
    db: Session, employee_id: int, year: int, month: int, actor
) -> Payslip:
    """Create one Payslip row for (employee_id, year, month).

    Caller is responsible for tenant-checking the employee BEFORE calling
    (routers do this via assert_can_access_employee). This function
    enforces the data-side invariants:

      - month is 1..12
      - no existing payslip for this period
      - a SalaryStructure is active on the last day of the period
    """
    if not 1 <= month <= 12:
        raise HTTPException(400, "month must be in 1..12")

    existing = (
        db.query(Payslip)
        .filter(
            Payslip.employee_id == employee_id,
            Payslip.year == year,
            Payslip.month == month,
            Payslip.deleted_at.is_(None),
        )
        .first()
    )
    if existing:
        raise HTTPException(
            400,
            f"Payslip for {year}-{month:02d} already exists for employee "
            f"{employee_id}. Delete it before regenerating."
        )

    as_of = _last_day_of_month(year, month)
    structure = get_current_structure(db, employee_id, as_of=as_of)
    if structure is None:
        raise HTTPException(
            400,
            f"No salary structure active for employee {employee_id} on "
            f"{as_of.isoformat()}. Create one first."
        )

    # ---- Attendance pro-rating ------------------------------------
    #
    # days_in_period  : calendar days in the month (28..31)
    # days_lwp        : days marked `absent` in attendance ledger
    # days_worked     : days_in_period - days_lwp (clamped to >= 0)
    # factor          : days_worked / days_in_period
    #
    # Earnings get pro-rated by `factor`. Deductions stay flat — PF /
    # professional tax / TDS / other deductions are computed off the
    # declared structure, not off pro-rated pay (matches typical
    # Indian payroll convention).
    #
    # The component fields stored on the Payslip reflect ACTUAL paid
    # amounts, not declared structure values. The structure values are
    # always retrievable via SalaryStructure history if needed.
    _, days_in_period = monthrange(year, month)

    # Look up the employee for company_id so _count_absent_days can
    # consult the holiday calendar. The structure is bound to this
    # employee_id, so the row is guaranteed to exist.
    employee = (
        db.query(Employee)
        .filter(Employee.id == employee_id, Employee.deleted_at.is_(None))
        .first()
    )
    company_id = employee.company_id if employee else None

    days_lwp = float(
        _count_absent_days(db, employee_id, company_id, year, month)
    )
    days_worked = max(0.0, days_in_period - days_lwp)
    factor = days_worked / days_in_period if days_in_period > 0 else 1.0

    basic_paid = structure.basic * factor
    hra_paid = structure.hra * factor
    special_paid = structure.special_allowance * factor
    other_paid = structure.other_allowances * factor

    gross = basic_paid + hra_paid + special_paid + other_paid
    total_deductions = (
        structure.pf
        + structure.professional_tax
        + structure.tds
        + structure.other_deductions
    )
    net = gross - total_deductions

    payslip = Payslip(
        employee_id=employee_id,
        year=year,
        month=month,
        # Pro-rated earnings (declared × factor)
        basic=basic_paid,
        hra=hra_paid,
        special_allowance=special_paid,
        other_allowances=other_paid,
        # Snapshotted deductions (flat)
        pf=structure.pf,
        professional_tax=structure.professional_tax,
        tds=structure.tds,
        other_deductions=structure.other_deductions,
        # Computed
        gross=gross,
        total_deductions=total_deductions,
        net=net,
        # Actual attendance numbers
        days_in_period=days_in_period,
        days_worked=days_worked,
        days_lwp=days_lwp,
        generated_at=datetime.now(timezone.utc),
        created_by=actor.id,
    )

    db.add(payslip)
    db.flush()  # populate id for the audit snapshot
    log_audit(
        db, actor=actor, action="payslip.generate",
        entity_type="payslip", entity_id=payslip.id,
        company_id=company_id, after=snapshot(payslip),
    )
    db.commit()
    db.refresh(payslip)
    return payslip


def generate_for_company(
    db: Session, company_id: int, year: int, month: int, actor
) -> tuple[list[Payslip], list[dict]]:
    """Bulk-generate payslips for every staff/employee in `company_id`.

    Continues on individual failures (missing structure, existing payslip)
    rather than aborting — caller gets both lists back. Each
    successful generation commits independently, so a partial-success
    run is durable.

    Returns (generated, skipped) where each item in `skipped` is a
    {"employee_id": int, "reason": str} dict.
    """
    employees = (
        db.query(Employee)
        .filter(
            Employee.company_id == company_id,
            Employee.deleted_at.is_(None),
            Employee.user_type.in_([UserTypes.staff, UserTypes.employee]),
        )
        .all()
    )

    generated: list[Payslip] = []
    skipped: list[dict] = []
    for emp in employees:
        try:
            generated.append(generate_payslip(db, emp.id, year, month, actor))
        except HTTPException as exc:
            skipped.append({"employee_id": emp.id, "reason": str(exc.detail)})

    return generated, skipped
