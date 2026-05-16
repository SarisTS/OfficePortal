"""Tests for the /reports/* endpoints."""
from datetime import date

import pytest

from app.models.attendance import Attendance, AttendanceStatus
from app.models.company import Company
from app.models.employee import Employee, UserTypes
from app.models.role import Role
from app.utils.hash import hash_password


ADMIN_EMAIL = "reports-admin@example.com"
EMP_EMAIL = "reports-emp@example.com"
EMP_ROLL = "EMP-RPT-001"
SUPER_EMAIL = "reports-super@example.com"
PASSWORD = "TestPass123!"


def _attendance(employee_id, company_id, day, status, hours=8.0, late=0):
    return Attendance(
        employee_id=employee_id,
        company_id=company_id,
        date=date(2026, 2, day),
        attendance_status=status,
        working_hours=hours,
        late_minutes=late,
    )


@pytest.fixture()
def stack(db_session):
    role = Role(role_name="DefaultRole")
    db_session.add(role)
    db_session.commit()
    db_session.refresh(role)

    company = Company(name="Acme")
    db_session.add(company)
    db_session.commit()
    db_session.refresh(company)

    admin = Employee(
        name="Admin",
        email=ADMIN_EMAIL,
        password_hash=hash_password(PASSWORD),
        user_type=UserTypes.office_admin,
        role_id=role.id,
        company_id=company.id,
        is_verified=True,
    )
    employee = Employee(
        name="Employee A",
        email=EMP_EMAIL,
        roll_no=EMP_ROLL,
        password_hash=hash_password(PASSWORD),
        user_type=UserTypes.employee,
        role_id=role.id,
        company_id=company.id,
        is_verified=True,
    )
    super_admin = Employee(
        name="Super",
        email=SUPER_EMAIL,
        password_hash=hash_password(PASSWORD),
        user_type=UserTypes.super_admin,
        role_id=role.id,
        is_verified=True,
    )
    db_session.add_all([admin, employee, super_admin])
    db_session.commit()
    db_session.refresh(admin)
    db_session.refresh(employee)
    db_session.refresh(super_admin)

    # Feb 2026: 5 present, 2 late (30 min each), 1 absent, 1 half_day, 1 leave
    attendances = [
        _attendance(employee.id, company.id, d, AttendanceStatus.present, 8.0)
        for d in range(1, 6)
    ]
    attendances += [
        _attendance(employee.id, company.id, d, AttendanceStatus.late, 7.0, 30)
        for d in (6, 7)
    ]
    attendances += [
        _attendance(employee.id, company.id, 8, AttendanceStatus.absent, 0),
        _attendance(employee.id, company.id, 9, AttendanceStatus.half_day, 4.0),
        _attendance(employee.id, company.id, 10, AttendanceStatus.leave, 0),
    ]
    db_session.add_all(attendances)
    db_session.commit()

    return {
        "admin": admin,
        "employee": employee,
        "super_admin": super_admin,
        "company": company,
    }


def _login(client, email: str) -> str:
    r = client.post(
        "/auth/admin/login", json={"email": email, "password": PASSWORD}
    )
    assert r.status_code == 200, r.text
    return r.json()["data"]["access_token"]


def _auth(token: str) -> dict:
    return {"Authorization": f"Bearer {token}"}


# ---------------------------------------------------------------------------

def test_company_monthly_attendance(client, stack):
    """office_admin: company-wide report for their own company."""
    fx = stack
    token = _login(client, ADMIN_EMAIL)

    r = client.get(
        "/reports/attendance/monthly?year=2026&month=2", headers=_auth(token)
    )
    assert r.status_code == 200, r.text
    items = r.json()["data"]
    assert len(items) == 1
    item = items[0]
    assert item["employee_id"] == fx["employee"].id
    assert item["employee_name"] == "Employee A"
    assert item["year"] == 2026
    assert item["month"] == 2

    assert item["days_present"] == 5
    assert item["days_late"] == 2
    assert item["days_absent"] == 1
    assert item["days_half_day"] == 1
    assert item["days_on_leave"] == 1
    # 5 × 8h + 2 × 7h + 4h = 58.0
    assert item["total_working_hours"] == 58.0
    # 2 × 30 min = 60
    assert item["total_late_minutes"] == 60


def test_employee_monthly_attendance(client, stack):
    fx = stack
    token = _login(client, ADMIN_EMAIL)

    r = client.get(
        f"/reports/attendance/employee/{fx['employee'].id}/monthly?year=2026&month=2",
        headers=_auth(token),
    )
    assert r.status_code == 200, r.text
    item = r.json()["data"]
    assert item["days_present"] == 5
    assert item["days_late"] == 2
    assert item["total_late_minutes"] == 60


def test_employee_with_no_data_returns_zeros_not_404(client, stack):
    """Reports should show a zero row, not error out, when there's no
    attendance data for the period."""
    fx = stack
    token = _login(client, ADMIN_EMAIL)

    r = client.get(
        f"/reports/attendance/employee/{fx['employee'].id}/monthly?year=2025&month=12",
        headers=_auth(token),
    )
    assert r.status_code == 200, r.text
    item = r.json()["data"]
    assert item["employee_id"] == fx["employee"].id
    assert item["employee_name"] == "Employee A"
    assert item["days_present"] == 0
    assert item["days_absent"] == 0
    assert item["total_working_hours"] == 0


def test_super_admin_requires_company_id(client, stack):
    """super_admin must pass company_id explicitly — no implicit
    cross-tenant report."""
    token = _login(client, SUPER_EMAIL)

    r = client.get(
        "/reports/attendance/monthly?year=2026&month=2", headers=_auth(token)
    )
    assert r.status_code == 400
    assert "company_id" in r.json()["message"].lower()


def test_super_admin_with_company_id(client, stack):
    """super_admin + company_id query param works."""
    fx = stack
    token = _login(client, SUPER_EMAIL)

    r = client.get(
        f"/reports/attendance/monthly?year=2026&month=2&company_id={fx['company'].id}",
        headers=_auth(token),
    )
    assert r.status_code == 200, r.text
    items = r.json()["data"]
    assert len(items) == 1
    assert items[0]["days_present"] == 5


def test_office_admin_company_id_param_is_ignored(client, stack, db_session):
    """office_admin: even if they pass company_id, the handler uses
    their own. Confirms cross-tenant leak isn't possible via the query
    param."""
    fx = stack

    # Create another company with one employee + attendance
    role = db_session.query(Role).first()
    other_company = Company(name="OtherCo")
    db_session.add(other_company)
    db_session.commit()
    db_session.refresh(other_company)

    other_emp = Employee(
        name="Other Co Emp",
        email="other-co-rpt@example.com",
        password_hash=hash_password(PASSWORD),
        user_type=UserTypes.employee,
        role_id=role.id,
        company_id=other_company.id,
        is_verified=True,
    )
    db_session.add(other_emp)
    db_session.commit()
    db_session.refresh(other_emp)

    db_session.add(
        _attendance(other_emp.id, other_company.id, 1, AttendanceStatus.present)
    )
    db_session.commit()

    # office_admin in company_a tries to peek at other_company.
    token = _login(client, ADMIN_EMAIL)
    r = client.get(
        f"/reports/attendance/monthly?year=2026&month=2&company_id={other_company.id}",
        headers=_auth(token),
    )
    assert r.status_code == 200, r.text
    items = r.json()["data"]
    # Response only contains the office_admin's OWN company's data.
    assert all(item["employee_id"] == fx["employee"].id for item in items)
    employee_ids = {item["employee_id"] for item in items}
    assert other_emp.id not in employee_ids


def test_soft_deleted_attendance_is_excluded(client, stack, db_session):
    """Soft-deleted attendance rows must not count in the aggregation."""
    fx = stack

    # Add one more present day, then soft-delete it
    extra = _attendance(
        fx["employee"].id, fx["company"].id, 11, AttendanceStatus.present
    )
    db_session.add(extra)
    db_session.commit()
    db_session.refresh(extra)

    from datetime import datetime, timezone
    extra.deleted_at = datetime.now(timezone.utc)
    db_session.commit()

    token = _login(client, ADMIN_EMAIL)
    r = client.get(
        "/reports/attendance/monthly?year=2026&month=2", headers=_auth(token)
    )
    assert r.status_code == 200, r.text
    item = r.json()["data"][0]
    # Still 5 present (the deleted one doesn't count)
    assert item["days_present"] == 5
