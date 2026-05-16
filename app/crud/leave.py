from sqlalchemy.orm import Session, joinedload
from fastapi import HTTPException
from datetime import datetime, timezone
from app.models.leave import Leave, LeaveStatus
from app.models.employee import Employee, UserTypes
from app.schemas.leave import LeaveCreate, LeaveUpdate, LeaveResponse
from app.crud.attendance import apply_leave_to_attendance
from app.crud.auth import is_global_admin
from app.services.leave_balance import (
    assert_can_debit, billable_leave_days, debit, get_or_init_balance, refund,
)


def _leave_with_employee(db: Session, leave_id: int):
    """Fetch a Leave with its employee eagerly loaded.

    Several callers immediately read ``leave.employee.company_id`` for the
    tenant check; doing this in one round-trip avoids the lazy SELECT.
    """
    return (
        db.query(Leave)
        .options(joinedload(Leave.employee))
        .filter(Leave.id == leave_id, Leave.deleted_at == None)
        .first()
    )

def create_leave(db: Session, leave: LeaveCreate, user) -> LeaveResponse:

    if leave.start_date > leave.end_date:
        raise HTTPException(400, "Invalid date range")

    # 🔒 Get employee
    employee = db.query(Employee).filter(
        Employee.id == leave.employee_id,
        Employee.deleted_at == None
    ).first()

    if not employee:
        raise HTTPException(404, "Employee not found")

    # 🔐 ACCESS CONTROL

    # 👤 Employee → only self
    if user.user_type in (UserTypes.staff, UserTypes.employee):
        if leave.employee_id != user.id:
            raise HTTPException(403, "Not allowed")

    # 🏢 Office Admin → same company only
    elif not is_global_admin(user):
        if user.company_id != employee.company_id:
            raise HTTPException(403, "Not allowed")

    # 🌍 Super Admin → allowed everywhere (no restriction)

    # ❌ Overlapping leave check
    overlapping = db.query(Leave).filter(
        Leave.employee_id == leave.employee_id,
        Leave.deleted_at == None,
        Leave.status != LeaveStatus.rejected,
        Leave.start_date <= leave.end_date,
        Leave.end_date >= leave.start_date
    ).first()

    if overlapping:
        raise HTTPException(400, "Overlapping leave exists")

    # 💰 Balance gate — refuse before the row enters `pending`. Debit
    # happens later on approval, not now; we only assert the employee
    # COULD afford this if approved today. require_policy() inside
    # get_or_init_balance raises 400 if the company has no policy.
    is_half_day = bool(getattr(leave, "is_half_day", False))
    days = billable_leave_days(
        db, employee.company_id,
        leave.start_date, leave.end_date, is_half_day,
    )
    balance = get_or_init_balance(
        db,
        employee_id=employee.id,
        company_id=employee.company_id,
        year=leave.start_date.year,
        leave_type=leave.leave_type,
    )
    assert_can_debit(balance, days)

    db_leave = Leave(**leave.model_dump())
    db_leave.created_by = user.id

    db.add(db_leave)
    db.commit()
    db.refresh(db_leave)

    return db_leave


def approve_leave(db: Session, leave_id: int, admin)-> LeaveResponse:

    leave = _leave_with_employee(db, leave_id)

    if not leave:
        raise HTTPException(404, "Leave not found")

    # 🔒 Tenant check — office_admin can only approve in their company.
    if not is_global_admin(admin):
        if leave.employee.company_id != admin.company_id:
            raise HTTPException(403, "Not allowed")

    if leave.status != LeaveStatus.pending:
        raise HTTPException(400, "Already processed")

    # 💰 Re-check + debit balance. Re-validating here (not just trusting
    # the gate at create-time) handles the case where allocation was
    # reduced between request and approval — or holidays were added
    # between the two events.
    days = billable_leave_days(
        db, leave.employee.company_id,
        leave.start_date, leave.end_date, bool(leave.is_half_day),
    )
    balance = get_or_init_balance(
        db,
        employee_id=leave.employee_id,
        company_id=leave.employee.company_id,
        year=leave.start_date.year,
        leave_type=leave.leave_type,
    )
    assert_can_debit(balance, days)

    leave.status = LeaveStatus.approved
    leave.approved_by = admin.id
    leave.approved_at = datetime.now(timezone.utc)

    # 🔗 Sync attendance + debit balance in one atomic unit so an attendance
    # failure rolls the balance back too.
    try:
        debit(balance, days)
        apply_leave_to_attendance(db, leave)
        db.commit()
        db.refresh(leave)
        return leave
    except Exception:
        db.rollback()
        raise


def reject_leave(db: Session, leave_id: int, admin)-> LeaveResponse:

    leave = _leave_with_employee(db, leave_id)

    if not leave:
        raise HTTPException(404, "Leave not found")

    # 🔒 Tenant check — office_admin can only reject in their company.
    if not is_global_admin(admin):
        if leave.employee.company_id != admin.company_id:
            raise HTTPException(403, "Not allowed")

    if leave.status != LeaveStatus.pending:
        raise HTTPException(400, "Already processed")

    leave.status = LeaveStatus.rejected
    leave.approved_by = admin.id
    leave.approved_at = datetime.now(timezone.utc)

    db.commit()
    db.refresh(leave)

    return leave


def get_leave(db: Session, leave_id: int, user):

    leave = _leave_with_employee(db, leave_id)

    if not leave:
        return None

    if user.user_type in (UserTypes.staff, UserTypes.employee):
        if leave.employee_id != user.id:
            raise HTTPException(403, "Not allowed")

    elif not is_global_admin(user):
        if leave.employee.company_id != user.company_id:
            raise HTTPException(403, "Not allowed")

    return leave


def get_leaves(db: Session, user, skip=0, limit=10):

    query = db.query(Leave).filter(Leave.deleted_at == None)

    if user.user_type in (UserTypes.staff, UserTypes.employee):
        query = query.filter(Leave.employee_id == user.id)

    elif not is_global_admin(user):
        query = query.join(Employee).filter(
            Employee.company_id == user.company_id
        )

    return query.order_by(Leave.id.desc()).offset(skip).limit(limit).all()


def get_employee_leaves(db: Session, employee_id: int, user):

    employee = db.query(Employee).filter(
        Employee.id == employee_id,
        Employee.deleted_at == None
    ).first()

    if not employee:
        raise HTTPException(404, "Employee not found")

    if user.user_type in (UserTypes.staff, UserTypes.employee):
        if employee_id != user.id:
            raise HTTPException(403, "Not allowed")

    elif not is_global_admin(user):
        if employee.company_id != user.company_id:
            raise HTTPException(403, "Not allowed")

    return db.query(Leave).filter(
        Leave.employee_id == employee_id,
        Leave.deleted_at == None
    ).order_by(Leave.start_date.desc()).all()


def update_leave(db: Session, leave_id: int, data: LeaveUpdate, user)-> LeaveResponse:

    leave = _leave_with_employee(db, leave_id)

    if not leave:
        return None
    
    if user.user_type in (UserTypes.staff, UserTypes.employee):
        if leave.employee_id != user.id:
            raise HTTPException(403, "Not allowed")

    elif not is_global_admin(user):
        if leave.employee.company_id != user.company_id:
            raise HTTPException(403, "Not allowed")

    # ❌ Cannot update approved/rejected
    if leave.status != LeaveStatus.pending:
        raise HTTPException(400, "Cannot modify processed leave")


    update_data = data.model_dump(exclude_unset=True)

    new_start = update_data.get("start_date", leave.start_date)
    new_end = update_data.get("end_date", leave.end_date)

    overlapping = db.query(Leave).filter(
        Leave.employee_id == leave.employee_id,
        Leave.id != leave.id,
        Leave.deleted_at == None,
        Leave.status != LeaveStatus.rejected,
        Leave.start_date <= new_end,
        Leave.end_date >= new_start
    ).first()

    if overlapping:
        raise HTTPException(400, "Overlapping leave exists")

    # ❌ Restrict fields
    forbidden = {"employee_id", "status", "approved_by", "approved_at"}
    for field in forbidden:
        if field in update_data:
            raise HTTPException(400, f"{field} cannot be updated")

    if "start_date" in update_data and "end_date" in update_data:
        if update_data["start_date"] > update_data["end_date"]:
            raise HTTPException(400, "Invalid date range")

    # 💰 If the date range changed, re-validate against balance. We're
    # still in pending state (enforced above), so no actual debit yet —
    # this is just the same affordability gate as create_leave.
    if "start_date" in update_data or "end_date" in update_data:
        new_days = billable_leave_days(
            db, leave.employee.company_id,
            new_start, new_end, bool(leave.is_half_day),
        )
        new_balance = get_or_init_balance(
            db,
            employee_id=leave.employee_id,
            company_id=leave.employee.company_id,
            year=new_start.year,
            leave_type=leave.leave_type,
        )
        assert_can_debit(new_balance, new_days)

    for key, value in update_data.items():
        setattr(leave, key, value)

    db.commit()
    db.refresh(leave)

    return leave


def delete_leave(db: Session, leave_id: int, user):

    leave = _leave_with_employee(db, leave_id)

    if not leave:
        return None

    if user.user_type in (UserTypes.staff, UserTypes.employee):
        if leave.employee_id != user.id:
            raise HTTPException(403, "Not allowed")

    elif not is_global_admin(user):
        if leave.employee.company_id != user.company_id:
            raise HTTPException(403, "Not allowed")

    # 💰 If the leave was approved, refund the balance before soft-deleting.
    # Previously this path was blocked entirely with "Cannot delete approved
    # leave"; the balance ledger gives us a clean way to cancel an approved
    # leave without losing accounting. (Rejected leaves never debited.)
    # Use billable_leave_days so the refund matches what was debited at
    # approval time (holidays inside the range were never charged).
    try:
        if leave.status == LeaveStatus.approved:
            days = billable_leave_days(
                db, leave.employee.company_id,
                leave.start_date, leave.end_date, bool(leave.is_half_day),
            )
            balance = get_or_init_balance(
                db,
                employee_id=leave.employee_id,
                company_id=leave.employee.company_id,
                year=leave.start_date.year,
                leave_type=leave.leave_type,
            )
            refund(balance, days)

        leave.deleted_at = datetime.now(timezone.utc)
        db.commit()
    except Exception:
        db.rollback()
        raise

    return leave