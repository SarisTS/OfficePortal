from app.models.attendance import Attendance
from datetime import date

def get_employee_monthly_report(db, employee_id, month, year):

    start_date = date(year, month, 1)
    end_date = date(year, month, 31)

    records = db.query(Attendance).filter(
        Attendance.employee_id == employee_id,
        Attendance.date.between(start_date, end_date)
    ).all()

    total_days = len(records)
    present = sum(1 for r in records if r.attendance_status == "present")
    late = sum(1 for r in records if r.attendance_status == "late")

    return {
        "total_days": total_days,
        "present": present,
        "late": late
    }

def get_company_report(db, company_id, date):

    return db.query(Attendance).filter(
        Attendance.company_id == company_id,
        Attendance.date == date
    ).all()