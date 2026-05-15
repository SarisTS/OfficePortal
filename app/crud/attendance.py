from sqlalchemy.orm import Session, joinedload
from sqlalchemy import or_
from fastapi import HTTPException
from datetime import datetime, timedelta, timezone

from app.database.database import with_transaction
from app.models.attendance import Attendance, AttendanceStatus
from app.models.assignment import EmployeeShiftAssignment
from app.models.employee import Employee, UserTypes
from app.schemas.attendance import AttendanceUpdate
from app.crud.auth import is_global_admin


def _active_shift_id_for(db: Session, employee_id: int, on_date) -> int | None:
    """Return the EmployeeShiftAssignment.shift_id active on `on_date`, or None."""
    row = (
        db.query(EmployeeShiftAssignment)
        .filter(
            EmployeeShiftAssignment.employee_id == employee_id,
            EmployeeShiftAssignment.start_date <= on_date,
            or_(
                EmployeeShiftAssignment.end_date.is_(None),
                EmployeeShiftAssignment.end_date >= on_date,
            ),
        )
        .first()
    )
    return row.shift_id if row else None

# NOTE: check-in / check-out used to live here as an AttendanceService class,
# duplicating app/services/attendance_service.py. The routers only ever called
# the services/ version, so the duplicate class was deleted in Phase 4. This
# module now holds only the read/update/delete/manual-mark/leave-sync helpers.


def get_attendance(db: Session, attendance_id: int, user):

    # joinedload(Attendance.employee) — the tenant check below reads
    # attendance.employee.company_id, which would otherwise trigger a
    # second SELECT per call.
    attendance = (
        db.query(Attendance)
        .options(joinedload(Attendance.employee))
        .filter(
            Attendance.id == attendance_id,
            Attendance.deleted_at == None,
        )
        .first()
    )

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

    attendance = (
        db.query(Attendance)
        .options(joinedload(Attendance.employee))
        .filter(
            Attendance.id == attendance_id,
            Attendance.deleted_at == None,
        )
        .first()
    )

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

    attendance = (
        db.query(Attendance)
        .options(joinedload(Attendance.employee))
        .filter(
            Attendance.id == attendance_id,
            Attendance.deleted_at == None,
        )
        .first()
    )

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

    # An employee/staff user must belong to a company per the
    # check_company_required constraint, but defend explicitly anyway —
    # super_admin manual-marking an admin user wouldn't have a company.
    if employee.company_id is None:
        raise HTTPException(
            400, "Cannot mark attendance for a user with no company"
        )

    attendance = db.query(Attendance).filter(
        Attendance.employee_id == employee_id,
        Attendance.date == date,
        Attendance.deleted_at == None,
    ).first()

    is_new = attendance is None

    with with_transaction(db):
        if is_new:
            attendance = Attendance(
                employee_id=employee_id,
                # NOT NULL on the schema — previously omitted, causing the
                # INSERT to fail. Sourced from the employee record.
                company_id=employee.company_id,
                # Best-effort: tag the active shift on that date if one
                # exists. Nullable, so None is acceptable.
                shift_id=_active_shift_id_for(db, employee_id, date),
                date=date,
            )
            db.add(attendance)

        attendance.check_in = data.check_in
        attendance.check_out = data.check_out
        attendance.is_manual = True
        attendance.manual_reason = data.reason

        # Audit trail — was previously `attendance.marked_by`, which is not a
        # column on the Attendance model (it would silently set a Python attr
        # and never persist). Use the AuditMixin fields instead.
        if is_new:
            attendance.created_by = admin.id
        attendance.updated_by = admin.id

        if attendance.check_in and attendance.check_out:
            seconds = (attendance.check_out - attendance.check_in).total_seconds()
            if seconds < 0:
                raise HTTPException(400, "check_out must be after check_in")
            attendance.working_hours = round(seconds / 3600, 2)

    db.refresh(attendance)
    return attendance


def apply_leave_to_attendance(db, leave):
    """Mark every day in [leave.start_date, leave.end_date] as LEAVE.

    Called from inside approve_leave's transaction — do NOT commit here.
    The caller is responsible for committing or rolling back the whole
    approve_leave + apply unit atomically.
    """

    # Resolve company_id once. Required because new Attendance rows have
    # company_id NOT NULL, and the previous implementation omitted it,
    # causing the INSERT to fail when no attendance row pre-existed.
    employee = db.query(Employee).filter(
        Employee.id == leave.employee_id,
        Employee.deleted_at == None,
    ).first()
    if not employee or employee.company_id is None:
        raise HTTPException(
            400, "Cannot apply leave: employee or employee.company missing"
        )

    current = leave.start_date

    while current <= leave.end_date:

        attendance = db.query(Attendance).filter(
            Attendance.employee_id == leave.employee_id,
            Attendance.date == current,
            Attendance.deleted_at == None,
        ).first()

        if not attendance:
            attendance = Attendance(
                employee_id=leave.employee_id,
                company_id=employee.company_id,
                shift_id=_active_shift_id_for(db, leave.employee_id, current),
                date=current,
            )
            db.add(attendance)

        attendance.attendance_status = AttendanceStatus.leave

        current += timedelta(days=1)