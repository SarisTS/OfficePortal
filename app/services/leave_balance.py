"""Helpers shared by leave-balance code paths.

The single source of truth for:

  - how many days a given (start, end, half_day) leave consumes
  - looking up / lazily seeding a LeaveBalance row
  - debit / refund of `used` (used by approve and cancel-approved)
  - "can we afford this?" check

Keeps these out of the routers and the existing crud/leave.py so the
balance arithmetic lives in one testable place.
"""

from __future__ import annotations

from datetime import date

from fastapi import HTTPException
from sqlalchemy.orm import Session

from app.models.leave import LeaveBalance, LeavePolicy, LeaveType


# ---------------------------------------------------------------------------
# Day counting
# ---------------------------------------------------------------------------

def compute_leave_days(start_date: date, end_date: date, is_half_day: bool) -> float:
    """Pure-math day count — calendar days inclusive, half-day → 0.5.

    Does NOT consult the holiday calendar; for that, use
    billable_leave_days() which wraps this and subtracts holidays.

    Float so half-day math works without rounding.
    """
    if end_date < start_date:
        raise ValueError("end_date must be >= start_date")

    if is_half_day:
        # A half-day request is a single day by convention; ignore any
        # multi-day range the caller might have set on a half_day=True.
        return 0.5

    return float((end_date - start_date).days + 1)


def billable_leave_days(
    db: Session,
    company_id: int | None,
    start_date: date,
    end_date: date,
    is_half_day: bool,
) -> float:
    """compute_leave_days minus any holidays falling inside [start, end]
    for the employee's company.

    Half-day leaves short-circuit at 0.5 (they're a single half-day by
    convention — holidays don't apply). If company_id is None (e.g. the
    actor isn't bound to a company, which shouldn't happen for leave-
    takers but defends defensively), holidays are NOT subtracted.

    All-holidays case: a 3-day leave whose days are all holidays
    debits 0 from the balance — the Leave row is still recorded for
    audit but the ledger is untouched (they didn't actually take any
    leave).
    """
    raw = compute_leave_days(start_date, end_date, is_half_day)
    if is_half_day or company_id is None:
        return raw

    # Import lazily so this module doesn't pull crud/holiday at module
    # load (avoids a potential circular import if crud/holiday ever
    # needs to call back into leave_balance).
    from app.crud.holiday import holiday_dates_in_range

    holidays = holiday_dates_in_range(db, company_id, start_date, end_date)
    return float(max(0.0, raw - len(holidays)))


# ---------------------------------------------------------------------------
# Policy + balance lookups
# ---------------------------------------------------------------------------

def get_policy(
    db: Session, company_id: int, leave_type: LeaveType
) -> LeavePolicy | None:
    """Active policy for a (company, leave_type) pair, or None."""
    return (
        db.query(LeavePolicy)
        .filter(
            LeavePolicy.company_id == company_id,
            LeavePolicy.leave_type == leave_type,
            LeavePolicy.deleted_at.is_(None),
        )
        .first()
    )


def require_policy(
    db: Session, company_id: int, leave_type: LeaveType
) -> LeavePolicy:
    """Same as get_policy but raises a 400 with a clear message."""
    policy = get_policy(db, company_id, leave_type)
    if policy is None:
        raise HTTPException(
            400,
            f"No leave policy configured for {leave_type.value} leave. "
            f"Ask an admin to create one before requesting this type."
        )
    return policy


def get_or_init_balance(
    db: Session,
    employee_id: int,
    company_id: int,
    year: int,
    leave_type: LeaveType,
) -> LeaveBalance:
    """Find or lazy-create the ledger row for (employee, year, leave_type).

    On first read for a given combo, seeds `allocated` from the matching
    LeavePolicy. Raises 400 via require_policy() if no policy exists.

    The caller is responsible for flushing/committing if they want the
    new row persisted across requests; this function only `db.add`s it
    and flushes to make the row queryable in the current session.
    """
    balance = (
        db.query(LeaveBalance)
        .filter(
            LeaveBalance.employee_id == employee_id,
            LeaveBalance.year == year,
            LeaveBalance.leave_type == leave_type,
            LeaveBalance.deleted_at.is_(None),
        )
        .first()
    )
    if balance is not None:
        return balance

    policy = require_policy(db, company_id, leave_type)
    balance = LeaveBalance(
        employee_id=employee_id,
        year=year,
        leave_type=leave_type,
        allocated=policy.annual_entitlement,
        used=0.0,
    )
    db.add(balance)
    # flush so subsequent reads in this transaction see the row, without
    # committing the whole unit of work — the caller controls that.
    db.flush()
    return balance


def remaining(balance: LeaveBalance) -> float:
    """Days still available on a balance row."""
    return float(balance.allocated) - float(balance.used)


# ---------------------------------------------------------------------------
# Mutations
# ---------------------------------------------------------------------------

def assert_can_debit(balance: LeaveBalance, days: float) -> None:
    """Raise 400 if the ledger doesn't have `days` to give."""
    if days > remaining(balance):
        raise HTTPException(
            400,
            f"Insufficient {balance.leave_type.value} leave balance: "
            f"requested {days}, available {remaining(balance):.1f}"
        )


def debit(balance: LeaveBalance, days: float) -> None:
    """Increment `used` by `days`. Caller must have already validated."""
    balance.used = float(balance.used) + days


def refund(balance: LeaveBalance, days: float) -> None:
    """Decrement `used` by `days`. Clamps at 0 to defend against any
    drift that could otherwise leave the ledger with negative `used`."""
    new_used = float(balance.used) - days
    balance.used = max(new_used, 0.0)
