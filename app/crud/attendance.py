from sqlalchemy.orm import Session
from fastapi import HTTPException
from datetime import datetime, timedelta, timezone

from app.models.attendance import Attendance, AttendanceStatus
from app.models.employee import Employee, UserTypes
from app.schemas.attendance import AttendanceUpdate
from app.crud.auth import is_global_admin

# NOTE: check-in / check-out used to live here as an AttendanceService class,
# duplicating app/services/attendance_service.py. The routers only ever called
# the services/ version, so the duplicate class was deleted in Phase 4. This
# module now holds only the read/update/delete/manual-mark/leave-sync helpers.


def get_attendance(db: Session, attendance_id: int, user):

    attendance = db.query(Attendance).filter(
        Attendance.id == attendance_id,
        Attendance.deleted_at == None
    ).first()

    if not attendance:
        return None

    # Previously `user.user_type == "employee"` compared an enum to a string
    # and always evaluated False, letting any non-admin reach the next branch
    # and 403 themselves only on a different check. Fix the comparison to use
    # the UserTypes enum so the self-only rule actually applies.
    if user.user_type in (UserTypes.staff, UserTypes.employee):
        if attendance.employee_id != user.id:
            raise HTTPException(403, "Not allowed")
    elif not is_global_admin(user):
        if attendance.employee.company_id != user.company_id:
            raise HTTPException(403, "Not allowed")

    return attendance


def get_employee_attendance(db: Session, employee_id: int, user):

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

    return db.query(Attendance).filter(
        Attendance.employee_id == employee_id,
        Attendance.deleted_at == None
    ).order_by(Attendance.date.desc()).all()


def update_attendance(db: Session, attendance_id: int, data: AttendanceUpdate, user):

    attendance = db.query(Attendance).filter(
        Attendance.id == attendance_id,
        Attendance.deleted_at == None
    ).first()

    if not attendance:
        return None

    if not is_global_admin(user):
        if attendance.employee.company_id != user.company_id:
            raise HTTPException(403, "Not allowed")

    forbidden = {"employee_id", "date"}
    update_data = data.model_dump(exclude_unset=True)

    for field in forbidden:
        if field in update_data:
            raise HTTPException(400, f"{field} cannot be updated")

    for key, value in update_data.items():
        setattr(attendance, key, value)

    db.commit()
    db.refresh(attendance)

    return attendance


def delete_attendance(db: Session, attendance_id: int, user):

    attendance = db.query(Attendance).filter(
        Attendance.id == attendance_id,
        Attendance.deleted_at == None
    ).first()

    if not attendance:
        return None

    if not is_global_admin(user):
        if attendance.employee.company_id != user.company_id:
            raise HTTPException(403, "Not allowed")

    attendance.deleted_at = datetime.now(timezone.utc)

    db.commit()

    return attendance


def mark_manual_attendance(db, employee_id, date, data, admin):

    employee = db.query(Employee).filter(
        Employee.id == employee_id,
        Employee.deleted_at == None
    ).first()

    if not employee:
        raise HTTPException(404, "Employee not found")

    if not is_global_admin(admin):
        if employee.company_id != admin.company_id:
            raise HTTPException(403, "Not allowed")

    attendance = db.query(Attendance).filter(
        Attendance.employee_id == employee_id,
        Attendance.date == date,
        Attendance.deleted_at == None
    ).first()

    if not attendance:
        attendance = Attendance(employee_id=employee_id, date=date)
        db.add(attendance)

    attendance.check_in = data.check_in
    attendance.check_out = data.check_out
    attendance.is_manual = True
    attendance.marked_by = admin.id
    attendance.manual_reason = data.reason

    if attendance.check_in and attendance.check_out:
        seconds = (attendance.check_out - attendance.check_in).total_seconds()
        attendance.working_hours = round(seconds / 3600, 2)

    db.commit()
    db.refresh(attendance)

    return attendance


def apply_leave_to_attendance(db, leave):

    current = leave.start_date

    while current <= leave.end_date:

        attendance = db.query(Attendance).filter(
            Attendance.employee_id == leave.employee_id,
            Attendance.date == current,
            Attendance.deleted_at == None
        ).first()

        if not attendance:
            attendance = Attendance(
                employee_id=leave.employee_id,
                date=current
            )
            db.add(attendance)

        attendance.attendance_status = AttendanceStatus.leave

        current += timedelta(days=1)