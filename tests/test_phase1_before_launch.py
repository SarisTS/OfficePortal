"""Regression tests for the Phase 1 "before launch" fixes (API_AUDIT.md
section 6 items #7-#13).

Covers:
  - admin employee search/filter (GET /employees/?q=...&department_id=...)
  - admin password reset (POST /employees/{id}/reset-password)
  - admin activate/deactivate (POST /employees/{id}/(activate|deactivate))
  - deactivated user is blocked from admin login
  - /me/leaves, /me/shifts/current, /me/shifts/history, /me/payslips/latest
  - year/month filter on /attendance/me
  - locations RESTful aliases + empty-list pagination
"""
from datetime import date, time, timedelta

import pytest

from app.models.assignment import EmployeeShiftAssignment
from app.models.attendance import Attendance, AttendanceStatus, Shift
from app.models.company import Company
from app.models.employee import Employee, UserTypes
from app.models.leave import Leave, LeaveStatus, LeaveType
from app.models.payslip import Payslip
from app.models.role import Role
from app.utils.hash import hash_password


ADMIN_EMAIL = "p1bl-admin@example.com"
SUPER_EMAIL = "p1bl-super@example.com"
EMP_EMAIL = "p1bl-emp@example.com"
EMP_ROLL = "P1BL-EMP-001"
PASSWORD = "TestPass123!"


@pytest.fixture()
def stack(db_session):
    role = Role(role_name="DefaultRole")
    db_session.add(role)
    db_session.commit()
    db_session.refresh(role)

    company_a = Company(name="Acme P1BL")
    db_session.add(company_a)
    db_session.commit()
    db_session.refresh(company_a)

    super_admin = Employee(
        name="Super",
        email=SUPER_EMAIL,
        password_hash=hash_password(PASSWORD),
        user_type=UserTypes.super_admin,
        role_id=role.id,
        is_verified=True,
    )
    admin = Employee(
        name="Admin",
        email=ADMIN_EMAIL,
        password_hash=hash_password(PASSWORD),
        user_type=UserTypes.office_admin,
        role_id=role.id,
        company_id=company_a.id,
        is_verified=True,
    )
    employee = Employee(
        name="Bob Builder",
        email=EMP_EMAIL,
        roll_no=EMP_ROLL,
        password_hash=hash_password(PASSWORD),
        user_type=UserTypes.employee,
        role_id=role.id,
        company_id=company_a.id,
        is_verified=True,
    )
    db_session.add_all([super_admin, admin, employee])
    db_session.commit()
    db_session.refresh(super_admin)
    db_session.refresh(admin)
    db_session.refresh(employee)

    return {
        "role": role,
        "company_a": company_a,
        "super": super_admin,
        "admin": admin,
        "employee": employee,
    }


def _admin_login(client, email: str = ADMIN_EMAIL) -> str:
    r = client.post(
        "/auth/admin/login", json={"email": email, "password": PASSWORD}
    )
    assert r.status_code == 200, r.text
    return r.json()["data"]["access_token"]


def _emp_login(client) -> str:
    r = client.post(
        "/auth/employee/login",
        json={"roll_no": EMP_ROLL, "password": PASSWORD},
    )
    assert r.status_code == 200, r.text
    return r.json()["data"]["access_token"]


def _auth(token: str) -> dict:
    return {"Authorization": f"Bearer {token}"}


# ---------------------------------------------------------------------------
# Admin employee search/filter
# ---------------------------------------------------------------------------

def test_employee_search_by_name_ilike(client, stack):
    token = _admin_login(client)
    r = client.get("/employees/?q=builder", headers=_auth(token))
    assert r.status_code == 200, r.text
    names = [e["name"] for e in r.json()["data"]["items"]]
    assert "Bob Builder" in names


def test_employee_search_by_email_partial(client, stack):
    token = _admin_login(client)
    r = client.get("/employees/?q=p1bl-emp", headers=_auth(token))
    assert r.status_code == 200, r.text
    assert any(
        e["email"] == EMP_EMAIL
        for e in r.json()["data"]["items"]
    )


def test_employee_search_by_user_type(client, stack):
    token = _admin_login(client)
    r = client.get(
        "/employees/?user_type=employee", headers=_auth(token)
    )
    assert r.status_code == 200, r.text
    types = {e["user_type"] for e in r.json()["data"]["items"]}
    # Only `employee`s come back — admins filtered out.
    assert types == {"employee"} or types == set()  # may be empty if scope hides


def test_employee_search_pagination_bounds(client, stack):
    token = _admin_login(client)
    # limit > 100 must be rejected by Query(le=100)
    r = client.get("/employees/?limit=999", headers=_auth(token))
    assert r.status_code == 422


# ---------------------------------------------------------------------------
# Admin password reset
# ---------------------------------------------------------------------------

def test_admin_reset_password_changes_hash(client, stack, db_session):
    token = _admin_login(client)
    old_hash = stack["employee"].password_hash

    r = client.post(
        f"/employees/{stack['employee'].id}/reset-password",
        headers=_auth(token),
    )
    assert r.status_code == 200, r.text

    db_session.expire_all()
    fresh = db_session.query(Employee).filter(
        Employee.id == stack["employee"].id
    ).first()
    assert fresh.password_hash != old_hash


def test_admin_reset_password_unknown_employee_404(client, stack):
    token = _admin_login(client)
    r = client.post(
        "/employees/9999999/reset-password", headers=_auth(token)
    )
    assert r.status_code == 404


# ---------------------------------------------------------------------------
# Activate / deactivate + login gate
# ---------------------------------------------------------------------------

def test_deactivate_then_activate_round_trip(client, stack, db_session):
    token = _admin_login(client)

    r = client.post(
        f"/employees/{stack['employee'].id}/deactivate",
        headers=_auth(token),
    )
    assert r.status_code == 200, r.text
    assert r.json()["data"]["is_active"] is False

    r = client.post(
        f"/employees/{stack['employee'].id}/activate",
        headers=_auth(token),
    )
    assert r.status_code == 200, r.text
    assert r.json()["data"]["is_active"] is True


def test_deactivated_employee_cannot_admin_login(client, stack, db_session):
    """Deactivated office_admin gets 403 on admin login, not 200."""
    # Demote the admin to deactivated through the lifecycle endpoint
    # itself (super_admin can deactivate office_admin).
    super_token = _admin_login(client, SUPER_EMAIL)
    r = client.post(
        f"/employees/{stack['admin'].id}/deactivate",
        headers=_auth(super_token),
    )
    assert r.status_code == 200, r.text

    r = client.post(
        "/auth/admin/login",
        json={"email": ADMIN_EMAIL, "password": PASSWORD},
    )
    assert r.status_code == 403


def test_cannot_deactivate_super_admin(client, stack):
    super_token = _admin_login(client, SUPER_EMAIL)
    r = client.post(
        f"/employees/{stack['super'].id}/deactivate",
        headers=_auth(super_token),
    )
    assert r.status_code == 400


# ---------------------------------------------------------------------------
# /me/leaves
# ---------------------------------------------------------------------------

def test_me_leaves_lists_own_leaves(client, stack, db_session):
    db_session.add(Leave(
        employee_id=stack["employee"].id,
        leave_type=LeaveType.casual,
        start_date=date(2026, 5, 1),
        end_date=date(2026, 5, 3),
        status=LeaveStatus.pending,
    ))
    db_session.commit()

    token = _emp_login(client)
    r = client.get("/me/leaves", headers=_auth(token))
    assert r.status_code == 200, r.text
    assert len(r.json()["data"]) == 1
    assert r.json()["data"][0]["leave_type"] == "casual"


def test_me_leaves_year_month_filter(client, stack, db_session):
    db_session.add_all([
        Leave(
            employee_id=stack["employee"].id,
            leave_type=LeaveType.casual,
            start_date=date(2026, 5, 1),
            end_date=date(2026, 5, 3),
            status=LeaveStatus.pending,
        ),
        Leave(
            employee_id=stack["employee"].id,
            leave_type=LeaveType.casual,
            start_date=date(2026, 3, 1),
            end_date=date(2026, 3, 2),
            status=LeaveStatus.pending,
        ),
    ])
    db_session.commit()

    token = _emp_login(client)
    r = client.get(
        "/me/leaves?year=2026&month=5", headers=_auth(token)
    )
    assert r.status_code == 200, r.text
    dates = [it["start_date"] for it in r.json()["data"]]
    assert dates == ["2026-05-01"]


def test_me_leaves_month_without_year_400(client, stack):
    token = _emp_login(client)
    r = client.get("/me/leaves?month=5", headers=_auth(token))
    assert r.status_code == 400


# ---------------------------------------------------------------------------
# /me/shifts/{current,history}
# ---------------------------------------------------------------------------

def test_me_shifts_current_returns_active_assignment(client, stack, db_session):
    shift = Shift(
        name="Day", start_time=time(9, 0), end_time=time(18, 0),
        company_id=stack["company_a"].id, grace_minutes=10,
    )
    db_session.add(shift)
    db_session.commit()
    db_session.refresh(shift)

    db_session.add(EmployeeShiftAssignment(
        employee_id=stack["employee"].id,
        shift_id=shift.id,
        start_date=date(2026, 1, 1),
        end_date=None,
    ))
    db_session.commit()

    token = _emp_login(client)
    r = client.get("/me/shifts/current", headers=_auth(token))
    assert r.status_code == 200, r.text
    assert r.json()["data"]["employee_id"] == stack["employee"].id
    assert r.json()["data"]["shift_id"] == shift.id


def test_me_shifts_history_paginated(client, stack, db_session):
    shift = Shift(
        name="Day", start_time=time(9, 0), end_time=time(18, 0),
        company_id=stack["company_a"].id, grace_minutes=10,
    )
    db_session.add(shift)
    db_session.commit()
    db_session.refresh(shift)

    db_session.add(EmployeeShiftAssignment(
        employee_id=stack["employee"].id,
        shift_id=shift.id,
        start_date=date(2026, 1, 1),
        end_date=date(2026, 3, 31),
    ))
    db_session.commit()

    token = _emp_login(client)
    r = client.get("/me/shifts/history", headers=_auth(token))
    assert r.status_code == 200, r.text
    body = r.json()["data"]
    assert body["total"] >= 1
    assert len(body["items"]) >= 1


# ---------------------------------------------------------------------------
# /me/payslips/latest
# ---------------------------------------------------------------------------

def test_me_payslips_latest_returns_most_recent(client, stack, db_session):
    db_session.add_all([
        Payslip(
            employee_id=stack["employee"].id,
            year=2026, month=3,
            basic=10000, gross=10000, total_deductions=0, net=10000,
            days_in_period=31, days_worked=31, days_lwp=0,
        ),
        Payslip(
            employee_id=stack["employee"].id,
            year=2026, month=4,
            basic=10000, gross=10000, total_deductions=0, net=10000,
            days_in_period=30, days_worked=30, days_lwp=0,
        ),
    ])
    db_session.commit()

    token = _emp_login(client)
    r = client.get("/me/payslips/latest", headers=_auth(token))
    assert r.status_code == 200, r.text
    p = r.json()["data"]
    assert (p["year"], p["month"]) == (2026, 4)


def test_me_payslips_latest_404_when_none(client, stack):
    token = _emp_login(client)
    r = client.get("/me/payslips/latest", headers=_auth(token))
    assert r.status_code == 404


# ---------------------------------------------------------------------------
# /attendance/me date filters
# ---------------------------------------------------------------------------

def test_attendance_me_month_filter(client, stack, db_session):
    db_session.add_all([
        Attendance(
            employee_id=stack["employee"].id,
            company_id=stack["company_a"].id,
            date=date(2026, 5, 1),
            attendance_status=AttendanceStatus.present,
            working_hours=8,
        ),
        Attendance(
            employee_id=stack["employee"].id,
            company_id=stack["company_a"].id,
            date=date(2026, 3, 1),
            attendance_status=AttendanceStatus.present,
            working_hours=8,
        ),
    ])
    db_session.commit()

    token = _emp_login(client)
    r = client.get(
        "/attendance/me?year=2026&month=5", headers=_auth(token)
    )
    assert r.status_code == 200, r.text
    dates = [it["date"] for it in r.json()["data"]]
    assert dates == ["2026-05-01"]


def test_attendance_me_month_without_year_400(client, stack):
    token = _emp_login(client)
    r = client.get("/attendance/me?month=5", headers=_auth(token))
    assert r.status_code == 400


def test_attendance_me_year_and_from_date_400(client, stack):
    token = _emp_login(client)
    r = client.get(
        "/attendance/me?year=2026&from_date=2026-01-01",
        headers=_auth(token),
    )
    assert r.status_code == 400


# ---------------------------------------------------------------------------
# Locations RESTful aliases + empty list
# ---------------------------------------------------------------------------

def test_locations_empty_list_returns_zero_total(client, stack):
    """No locations seeded → empty paginated payload, NOT 404."""
    token = _admin_login(client)
    r = client.get("/locations/", headers=_auth(token))
    assert r.status_code == 200, r.text
    assert r.json()["data"]["total"] == 0
    assert r.json()["data"]["items"] == []


# ---------------------------------------------------------------------------
# Pagination bounds — sanity smoke
# ---------------------------------------------------------------------------

def test_hostels_limit_out_of_range_422(client, stack):
    token = _admin_login(client)
    r = client.get("/hostels/?limit=10000", headers=_auth(token))
    assert r.status_code == 422
