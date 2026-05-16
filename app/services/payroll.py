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
from sqlalchemy.orm import Session

from app.crud.salary_structure import get_current_structure
from app.models.employee import Employee, UserTypes
from app.models.payslip import Payslip


def _last_day_of_month(year: int, month: int) -> date:
    _, days = monthrange(year, month)
    return date(year, month, days)


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

    gross = (
        structure.basic
        + structure.hra
        + structure.special_allowance
        + structure.other_allowances
    )
    total_deductions = (
        structure.pf
        + structure.professional_tax
        + structure.tds
        + structure.other_deductions
    )
    net = gross - total_deductions

    _, days_in_period = monthrange(year, month)

    payslip = Payslip(
        employee_id=employee_id,
        year=year,
        month=month,
        # Snapshotted earnings
        basic=structure.basic,
        hra=structure.hra,
        special_allowance=structure.special_allowance,
        other_allowances=structure.other_allowances,
        # Snapshotted deductions
        pf=structure.pf,
        professional_tax=structure.professional_tax,
        tds=structure.tds,
        other_deductions=structure.other_deductions,
        # Computed
        gross=gross,
        total_deductions=total_deductions,
        net=net,
        # Informational attendance (no pro-rating yet)
        days_in_period=days_in_period,
        days_worked=float(days_in_period),
        days_lwp=0.0,
        generated_at=datetime.now(timezone.utc),
        created_by=actor.id,
    )

    db.add(payslip)
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
