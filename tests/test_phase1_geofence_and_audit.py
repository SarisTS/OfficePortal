"""Geo-fence end-to-end + role/department audit coverage tests.

Phase 1 stabilization closeout — covers API_AUDIT.md section 8
(check-in/check-out geo-fence verification) and section 7 (role +
department audit coverage gap).

Geo-fence design notes:
  - The test seeds a CompanyLocation at (12.9716, 77.5946) — Bangalore
    center — with a 100m radius.
  - Inside-radius test sends the exact same coords → distance 0.
  - Outside-radius test sends coords ~1km away (0.01° latitude offset).
  - Shift window is configured 00:00-23:59 so the test doesn't fail
    due to time-of-day. The check-in allowed window is
    [shift_start - 30min, shift_end + 60min], which spans well over
    24h with that config.
  - Each test runs in its own db_session rollback so the
    "active session already exists" guard doesn't bleed across.
"""
from datetime import date, time

import pytest

from app.models.assignment import CompanyLocation, EmployeeShiftAssignment
from app.models.attendance import Shift
from app.models.audit_log import AuditLog
from app.models.company import Company
from app.models.department import Department
from app.models.employee import Employee, UserTypes
from app.models.role import Role
from app.utils.hash import hash_password


SUPER_EMAIL = "geo-super@example.com"
ADMIN_EMAIL = "geo-admin@example.com"
EMP_EMAIL = "geo-emp@example.com"
EMP_ROLL = "GEO-EMP-001"
PASSWORD = "TestPass123!"

# Bangalore city centre — known to be on land, on a reasonable latitude,
# safely numerical (no edge cases at the poles or antimeridian).
SITE_LAT = 12.9716
SITE_LON = 77.5946


@pytest.fixture()
def stack(db_session):
    role = Role(role_name="DefaultRole")
    db_session.add(role)
    db_session.commit()
    db_session.refresh(role)

    company_a = Company(name="Acme Geo")
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
        name="Geo Emp",
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

    # 24h shift so check-in's time-of-day window is always satisfied.
    shift = Shift(
        name="All Day",
        start_time=time(0, 0),
        end_time=time(23, 59),
        company_id=company_a.id,
        grace_minutes=10,
    )
    db_session.add(shift)
    db_session.commit()
    db_session.refresh(shift)

    db_session.add(EmployeeShiftAssignment(
        employee_id=employee.id,
        shift_id=shift.id,
        start_date=date(2026, 1, 1),
        end_date=None,
    ))

    # The geo-fence: one site at Bangalore centre with a 100m radius.
    db_session.add(CompanyLocation(
        name="HQ",
        latitude=SITE_LAT,
        longitude=SITE_LON,
        radius=100,
        is_primary=True,
        company_id=company_a.id,
    ))
    db_session.commit()

    return {
        "role": role,
        "company_a": company_a,
        "super": super_admin,
        "admin": admin,
        "employee": employee,
        "shift": shift,
    }


def _admin_login(client, email=ADMIN_EMAIL) -> str:
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
# Geo-fence
# ---------------------------------------------------------------------------

def test_check_in_inside_radius_succeeds(client, stack):
    """Caller at exactly the configured site lat/lon → check-in 200."""
    token = _emp_login(client)
    r = client.post(
        "/attendance/check-in",
        json={"lat": SITE_LAT, "lon": SITE_LON},
        headers=_auth(token),
    )
    assert r.status_code == 200, r.text
    data = r.json()["data"]
    assert data["employee_id"] == stack["employee"].id


def test_check_in_outside_radius_rejected(client, stack):
    """0.01° latitude offset is ~1.1km — far outside the 100m radius
    configured on the site → 400."""
    token = _emp_login(client)
    r = client.post(
        "/attendance/check-in",
        json={"lat": SITE_LAT + 0.01, "lon": SITE_LON},
        headers=_auth(token),
    )
    assert r.status_code == 400
    assert "location" in r.json()["message"].lower()


def test_check_out_outside_radius_rejected(client, stack):
    """Check-in inside, then attempt check-out from outside the
    radius — must 400, not silently accept."""
    token = _emp_login(client)
    r = client.post(
        "/attendance/check-in",
        json={"lat": SITE_LAT, "lon": SITE_LON},
        headers=_auth(token),
    )
    assert r.status_code == 200, r.text

    r = client.post(
        "/attendance/check-out",
        json={"lat": SITE_LAT + 0.01, "lon": SITE_LON},
        headers=_auth(token),
    )
    assert r.status_code == 400
    assert "location" in r.json()["message"].lower()


def test_check_in_no_site_configured_400(client, stack, db_session):
    """If the company has no active sites, check-in should refuse
    rather than fall through to a free-for-all."""
    # Soft-delete the only site for this company.
    site = db_session.query(CompanyLocation).filter(
        CompanyLocation.company_id == stack["company_a"].id
    ).first()
    site.is_active = False
    db_session.commit()

    token = _emp_login(client)
    r = client.post(
        "/attendance/check-in",
        json={"lat": SITE_LAT, "lon": SITE_LON},
        headers=_auth(token),
    )
    assert r.status_code == 400
    assert "location" in r.json()["message"].lower()


# ---------------------------------------------------------------------------
# Role + Department audit coverage
# ---------------------------------------------------------------------------

def test_role_create_emits_audit(client, stack, db_session):
    token = _admin_login(client)
    r = client.post(
        "/roles/", json={"role_name": "Manager"}, headers=_auth(token)
    )
    assert r.status_code == 200, r.text
    role_id = r.json()["data"]["id"]

    log = (
        db_session.query(AuditLog)
        .filter(
            AuditLog.action == "role.create",
            AuditLog.entity_id == role_id,
        )
        .one()
    )
    assert log.actor_email == ADMIN_EMAIL
    assert log.after["role_name"] == "Manager"
    # Roles are global — no tenant on the audit row.
    assert log.company_id is None


def test_department_create_emits_audit(client, stack, db_session):
    token = _admin_login(client)
    r = client.post(
        "/departments/",
        json={
            "dept_name": "Engineering",
            "company_id": stack["company_a"].id,
        },
        headers=_auth(token),
    )
    assert r.status_code == 200, r.text
    dept_id = r.json()["data"]["id"]

    log = (
        db_session.query(AuditLog)
        .filter(
            AuditLog.action == "department.create",
            AuditLog.entity_id == dept_id,
        )
        .one()
    )
    assert log.actor_email == ADMIN_EMAIL
    assert log.company_id == stack["company_a"].id
    assert log.after["dept_name"] == "Engineering"


def test_department_delete_emits_audit(client, stack, db_session):
    dept = Department(
        dept_name="Soon-To-Delete",
        company_id=stack["company_a"].id,
    )
    db_session.add(dept)
    db_session.commit()
    db_session.refresh(dept)
    dept_id = dept.id

    token = _admin_login(client)
    r = client.delete(
        f"/departments/{dept_id}", headers=_auth(token)
    )
    assert r.status_code == 200, r.text

    log = (
        db_session.query(AuditLog)
        .filter(
            AuditLog.action == "department.delete",
            AuditLog.entity_id == dept_id,
        )
        .one()
    )
    assert log.company_id == stack["company_a"].id
    assert log.before is not None
    assert log.before["dept_name"] == "Soon-To-Delete"
