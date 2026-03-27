from sqlalchemy.orm import Session
from fastapi import HTTPException
from datetime import datetime, timedelta, timezone
from app.models.attendance import Attendance, Shift, AttendanceStatus
from app.models.employee import Employee
from app.models.leave import Leave, LeaveStatus
from app.schemas.attendance import AttendanceUpdate
from app.crud.auth import is_global_admin
from app.models.assignment import EmployeeShiftAssignment, CompanyLocation
from app.utils.distance import calculate_distance
from sqlalchemy import or_


class AttendanceService:

    @staticmethod
    def get_active_shift(db, employee_id, now):
        return db.query(EmployeeShiftAssignment).filter(
            EmployeeShiftAssignment.employee_id == employee_id,
            EmployeeShiftAssignment.start_date <= now.date(),
            or_(
                EmployeeShiftAssignment.end_date == None,
                EmployeeShiftAssignment.end_date >= now.date()
            )
        ).first()

    @staticmethod
    def validate_location(emp_lat, emp_lon, location):
        distance = calculate_distance(
            emp_lat, emp_lon,
            location.latitude, location.longitude
        )

        if distance > location.radius:
            raise HTTPException(400, "Outside allowed location")

    @staticmethod
    def check_in(db, employee, lat, lon):

        now = datetime.now(timezone.utc)

        # 🔹 Get shift
        assignment = AttendanceService.get_active_shift(db, employee.id, now)
        if not assignment:
            raise HTTPException(400, "No shift assigned")

        shift = assignment.shift

        # 🔹 Validate company
        if shift.company_id != employee.company_id:
            raise HTTPException(400, "Invalid shift")

        # 🔹 Get location (company level)
        location = db.query(CompanyLocation).filter(
            CompanyLocation.company_id == employee.company_id
        ).first()

        if not location:
            raise HTTPException(400, "No location configured")

        # 🔹 Geo-fencing
        AttendanceService.validate_location(lat, lon, location)

        # 🔹 Prevent duplicate
        attendance = db.query(Attendance).filter(
            Attendance.employee_id == employee.id,
            Attendance.date == now.date(),
            Attendance.deleted_at == None
        ).with_for_update().first()

        if attendance and attendance.check_in:
            return attendance

        if not attendance:
            attendance = Attendance(
                employee_id=employee.id,
                company_id=employee.company_id,
                shift_id=shift.id,
                date=now.date()
            )
            db.add(attendance)

        attendance.check_in = now
        attendance.check_in_lat = lat
        attendance.check_in_lon = lon
        attendance.location_id = location.id

        # 🔹 Late logic
        shift_start = datetime.combine(now.date(), shift.start_time)

        late_minutes = max(0, int((now - shift_start).total_seconds() / 60))

        if late_minutes > shift.grace_minutes:
            attendance.late_minutes = late_minutes
            attendance.attendance_status = AttendanceStatus.late

        db.commit()
        db.refresh(attendance)

        return attendance
    
    @staticmethod
    def check_out(db, employee, lat, lon):

        now = datetime.now(timezone.utc)

        attendance = db.query(Attendance).filter(
            Attendance.employee_id == employee.id,
            Attendance.check_in != None,
            Attendance.check_out == None
        ).with_for_update().first()

        if not attendance:
            raise HTTPException(400, "Check-in required")

        attendance.check_out = now
        attendance.check_out_lat = lat
        attendance.check_out_lon = lon

        # 🔹 Working hours
        seconds = (attendance.check_out - attendance.check_in).total_seconds()
        attendance.working_hours = round(seconds / 3600, 2)

        db.commit()
        db.refresh(attendance)

        return attendance


def get_attendance(db: Session, attendance_id: int, user):

    attendance = db.query(Attendance).filter(
        Attendance.id == attendance_id,
        Attendance.deleted_at == None
    ).first()

    if not attendance:
        return None

    if user.user_type == "employee":
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

    if user.user_type == "employee":
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