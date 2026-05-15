from datetime import datetime, timedelta
from fastapi import HTTPException
from sqlalchemy.orm import Session
from sqlalchemy import or_
import pytz

from app.core.config import settings
from app.models.assignment import EmployeeShiftAssignment, CompanyLocation
from app.models.attendance import Attendance, AttendanceStatus
from app.utils.distance import calculate_distance


# Resolved once at import. Settings is itself env-driven, defaulting to
# "Asia/Kolkata" so existing deployments are unaffected. Invalid zone
# names raise pytz.UnknownTimeZoneError here — that's intentional:
# fail-fast at startup beats silently mislocalizing every check-in.
LOCAL_TZ = pytz.timezone(settings.TIMEZONE)


class AttendanceService:

    # ---------------------------
    # 🔹 INTERNAL HELPERS
    # ---------------------------

    @staticmethod
    def now():
        return datetime.now(LOCAL_TZ)

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
    def validate_location(lat, lon, locations):
        for loc in locations:
            distance = calculate_distance(lat, lon, loc.latitude, loc.longitude)
            if distance <= loc.radius:
                return loc
        raise HTTPException(400, "Outside allowed location")

    @staticmethod
    def _get_shift_window(now, shift):
        """
        Returns shift_start and shift_end in the configured LOCAL_TZ.
        Handles night shifts correctly.
        """

        base_date = now.date()

        shift_start = LOCAL_TZ.localize(datetime.combine(base_date, shift.start_time))
        shift_end = LOCAL_TZ.localize(datetime.combine(base_date, shift.end_time))

        # 🌙 Night shift (cross midnight)
        if shift.end_time <= shift.start_time:
            shift_end += timedelta(days=1)

            # If current time is before shift_start, we are in post-midnight part
            if now < shift_start:
                shift_start -= timedelta(days=1)
                shift_end -= timedelta(days=1)

        return shift_start, shift_end

    @staticmethod
    def _get_locations(db, company_id):
        locations = db.query(CompanyLocation).filter(
            CompanyLocation.company_id == company_id,
            CompanyLocation.is_active == True,
            CompanyLocation.deleted_at == None
        ).all()

        if not locations:
            raise HTTPException(400, "No active locations configured")

        return locations

    # ---------------------------
    # 🔹 CHECK-IN
    # ---------------------------

    @staticmethod
    def check_in(db: Session, employee, lat, lon):

        now = AttendanceService.now()

        # 🔹 Get shift
        assignment = AttendanceService.get_active_shift(db, employee.id, now)
        if not assignment:
            raise HTTPException(400, "No shift assigned")

        shift = assignment.shift

        if shift.company_id != employee.company_id:
            raise HTTPException(400, "Invalid shift")

        # 🔹 Validate location
        locations = AttendanceService._get_locations(db, employee.company_id)
        valid_location = AttendanceService.validate_location(lat, lon, locations)

        # 🔹 Prevent multiple active sessions
        active = db.query(Attendance).filter(
            Attendance.employee_id == employee.id,
            Attendance.check_out == None,
            Attendance.deleted_at == None
        ).first()

        if active:
            return active

        # 🔹 Shift window
        shift_start, shift_end = AttendanceService._get_shift_window(now, shift)

        # 🛑 STRICT SHIFT VALIDATION
        early_buffer = timedelta(minutes=30)
        late_buffer = timedelta(minutes=60)

        allowed_start = shift_start - early_buffer
        allowed_end = shift_end + late_buffer

        if not (allowed_start <= now <= allowed_end):
            raise HTTPException(400, "Not within allowed shift time")

        attendance_date = shift_start.date()

        # 🔹 Lock row
        attendance = db.query(Attendance).filter(
            Attendance.employee_id == employee.id,
            Attendance.date == attendance_date,
            Attendance.deleted_at == None
        ).with_for_update().first()

        if not attendance:
            attendance = Attendance(
                employee_id=employee.id,
                company_id=employee.company_id,
                shift_id=shift.id,
                date=attendance_date
            )
            db.add(attendance)

        if attendance.check_in:
            return attendance

        # 🔹 Save check-in
        attendance.check_in = now
        attendance.check_in_lat = lat
        attendance.check_in_lon = lon
        attendance.company_location_id = valid_location.id

        # 🔹 Late calculation
        grace_time = shift_start + timedelta(minutes=shift.grace_minutes)

        if now > grace_time:
            late_minutes = int((now - grace_time).total_seconds() / 60)
            attendance.late_minutes = late_minutes
            attendance.attendance_status = AttendanceStatus.late
        else:
            attendance.late_minutes = 0
            attendance.attendance_status = AttendanceStatus.present

        db.commit()
        db.refresh(attendance)

        return attendance

    # ---------------------------
    # 🔹 CHECK-OUT
    # ---------------------------

    @staticmethod
    def check_out(db: Session, employee, lat, lon):

        now = AttendanceService.now()

        attendance = db.query(Attendance).filter(
            Attendance.employee_id == employee.id,
            Attendance.check_in != None,
            Attendance.check_out == None,
            Attendance.deleted_at == None
        ).with_for_update().first()

        if not attendance:
            raise HTTPException(400, "Check-in required")

        # 🔹 Validate location
        locations = AttendanceService._get_locations(db, employee.company_id)
        valid_location = AttendanceService.validate_location(lat, lon, locations)

        shift = attendance.shift

        # 🔹 Get correct shift window using attendance.date
        shift_start = LOCAL_TZ.localize(datetime.combine(attendance.date, shift.start_time))
        shift_end = LOCAL_TZ.localize(datetime.combine(attendance.date, shift.end_time))

        if shift.end_time <= shift.start_time:
            shift_end += timedelta(days=1)

        # 🔒 Checkout window restriction
        max_checkout_time = shift_end + timedelta(hours=3)

        if now > max_checkout_time:
            raise HTTPException(400, "Checkout window expired")

        # 🔹 Save checkout
        attendance.check_out = now
        attendance.check_out_lat = lat
        attendance.check_out_lon = lon
        attendance.checkout_location_id = valid_location.id

        # 🔹 Working hours
        seconds = (attendance.check_out - attendance.check_in).total_seconds()

        if seconds < 0:
            raise HTTPException(400, "Invalid checkout time")

        attendance.working_hours = round(seconds / 3600, 2)

        shift_hours = (shift_end - shift_start).total_seconds() / 3600

        # 🔹 Status logic
        if attendance.working_hours < 1:
            attendance.attendance_status = AttendanceStatus.absent
        elif attendance.working_hours < (shift_hours / 2):
            attendance.attendance_status = AttendanceStatus.half_day
        else:
            attendance.attendance_status = AttendanceStatus.present

        db.commit()
        db.refresh(attendance)

        return attendance