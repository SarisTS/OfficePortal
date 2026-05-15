from sqlalchemy.orm import Session
from fastapi import HTTPException
from datetime import datetime, timezone
from app.models.leave import Leave, LeaveStatus
from app.models.employee import Employee, UserTypes
from app.schemas.leave import LeaveCreate, LeaveUpdate, LeaveResponse
from app.crud.attendance import apply_leave_to_attendance
from app.crud.auth import is_global_admin

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

    db_leave = Leave(**leave.model_dump())
    db_leave.created_by = user.id

    db.add(db_leave)
    db.commit()
    db.refresh(db_leave)

    return db_leave


def approve_leave(db: Session, leave_id: int, admin)-> LeaveResponse:

    leave = db.query(Leave).filter(
        Leave.id == leave_id,
        Leave.deleted_at == None
    ).first()

    if not leave:
        raise HTTPException(404, "Leave not found")

    # 🔒 Tenant check — office_admin can only approve in their company.
    if not is_global_admin(admin):
        if leave.employee.company_id != admin.company_id:
            raise HTTPException(403, "Not allowed")

    if leave.status != LeaveStatus.pending:
        raise HTTPException(400, "Already processed")

    leave.status = LeaveStatus.approved
    leave.approved_by = admin.id
    leave.approved_at = datetime.now(timezone.utc)

    # 🔗 Sync attendance
    try:
        apply_leave_to_attendance(db, leave)
        db.commit()
        db.refresh(leave)
        return leave
    except Exception:
        db.rollback()
        raise
    

def reject_leave(db: Session, leave_id: int, admin)-> LeaveResponse:

    leave = db.query(Leave).filter(
        Leave.id == leave_id,
        Leave.deleted_at == None
    ).first()

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

    leave = db.query(Leave).filter(
        Leave.id == leave_id,
        Leave.deleted_at == None
    ).first()

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

    leave = db.query(Leave).filter(
        Leave.id == leave_id,
        Leave.deleted_at == None
    ).first()

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

    for key, value in update_data.items():
        setattr(leave, key, value)

    db.commit()
    db.refresh(leave)

    return leave


def delete_leave(db: Session, leave_id: int, user):

    leave = db.query(Leave).filter(
        Leave.id == leave_id,
        Leave.deleted_at == None
    ).first()

    if not leave:
        return None
    
    if user.user_type in (UserTypes.staff, UserTypes.employee):
        if leave.employee_id != user.id:
            raise HTTPException(403, "Not allowed")

    elif not is_global_admin(user):
        if leave.employee.company_id != user.company_id:
            raise HTTPException(403, "Not allowed")

    # ❌ Cannot delete approved leave
    if leave.status == LeaveStatus.approved:
        raise HTTPException(400, "Cannot delete approved leave")

    leave.deleted_at = datetime.now(timezone.utc)

    db.commit()

    return leave