"""Read + admin-adjust CRUD for LeaveBalance.

Write paths from leave creation/approval/cancellation live in
crud/leave.py — this module only exposes:

  - GET my balances for a year
  - GET balances for an arbitrary employee (admin, company-scoped)
  - POST manual adjustment (admin, audited via reason + updated_by)
"""
from datetime import date

from fastapi import HTTPException
from sqlalchemy.orm import Session

from app.core.permissions import (
    assert_can_access_employee, is_any_admin,
)
from app.database.database import with_transaction
from app.models.employee import Employee
from app.models.leave import LeaveBalance, LeaveType
from app.services.leave_balance import get_or_init_balance


def _resolve_year(year: int | None) -> int:
    return year if year is not None else date.today().year


def list_balances_for_employee(
    db: Session, target_employee_id: int, actor, year: int | None = None
):
    """All four (now: three) leave_types for an employee in a given year.

    Lazy-creates any missing rows by reading through get_or_init_balance,
    which seeds `allocated` from the matching LeavePolicy. If the
    company has no policy for a leave_type, that type is simply omitted
    from the response (rather than 400'ing the whole listing).
    """
    target = assert_can_access_employee(db, target_employee_id, actor)
    if target.company_id is None:
        # super_admin and office_admin sit outside any "owns leave"
        # company. They don't have balances to report.
        return _resolve_year(year), []

    year = _resolve_year(year)
    items: list[LeaveBalance] = []
    for lt in LeaveType:
        try:
            items.append(
                get_or_init_balance(
                    db,
                    employee_id=target.id,
                    company_id=target.company_id,
                    year=year,
                    leave_type=lt,
                )
            )
        except HTTPException as exc:
            # require_policy returns 400 when the company hasn't
            # configured a policy for this leave_type. That's not an
            # error for a listing — just skip it.
            if exc.status_code == 400:
                continue
            raise
    # Persist any rows that lazy-init created.
    db.commit()
    return year, items


def adjust_balance(
    db: Session,
    target_employee_id: int,
    data,
    actor: Employee,
) -> LeaveBalance:
    """Apply a signed delta to allocated. Audited via reason + updated_by.

    Use cases: joining mid-year, comp time, correcting a data error.
    Rare enough that we don't model it as its own table — the audit
    sits in the LeaveBalance row's updated_at / updated_by plus the
    request log.
    """
    if not is_any_admin(actor):
        raise HTTPException(403, "Admin role required")

    target = assert_can_access_employee(db, target_employee_id, actor)
    if target.company_id is None:
        raise HTTPException(
            400, "Target employee is not scoped to any company"
        )

    balance = get_or_init_balance(
        db,
        employee_id=target.id,
        company_id=target.company_id,
        year=data.year,
        leave_type=data.leave_type,
    )

    new_allocated = float(balance.allocated) + data.delta
    if new_allocated < float(balance.used):
        raise HTTPException(
            400,
            f"Adjustment would leave allocated ({new_allocated:.1f}) below "
            f"already-used ({balance.used:.1f}). Refund leaves first.",
        )

    with with_transaction(db):
        balance.allocated = new_allocated
        balance.updated_by = actor.id
        # The reason isn't stored in a dedicated column today; it's
        # captured via the request log + this commit's updated_at.
        # Adding a leave_balance_adjustments audit table is a small
        # follow-up if compliance ever asks.

    db.refresh(balance)
    return balance
