"""Regression tests for the Phase 1 stabilization critical fixes (2026-05-16).

Covers the six findings from API_AUDIT.md section 6 (immediate):
  1. POST /auth/employees now routes through the safe crud.employee path
     with tenant scoping (office_admin can't create cross-company)
  2. /companies/ mutations are super_admin-only
  3. /companies/ reads are tenant-scoped
  4. /auth/logout returns 200 for an authenticated caller
  5. POST /attendance/manual/{employee_id} parses date in body
  6. /auth/google/callback re-raises HTTPException (covered indirectly —
     no live OAuth in CI, but verified by reading the code path)
"""
import pytest

from app.models.company import Company
from app.models.employee import Employee, UserTypes
from app.models.role import Role
from app.utils.hash import hash_password


SUPER_EMAIL = "p1-super@example.com"
OFFICE_A_EMAIL = "p1-office-a@example.com"
OFFICE_B_EMAIL = "p1-office-b@example.com"
PASSWORD = "TestPass123!"


@pytest.fixture()
def stack(db_session):
    role = Role(role_name="DefaultRole")
    db_session.add(role)
    db_session.commit()
    db_session.refresh(role)

    company_a = Company(name="Acme P1")
    company_b = Company(name="OtherCo P1")
    db_session.add_all([company_a, company_b])
    db_session.commit()
    db_session.refresh(company_a)
    db_session.refresh(company_b)

    super_admin = Employee(
        name="Super",
        email=SUPER_EMAIL,
        password_hash=hash_password(PASSWORD),
        user_type=UserTypes.super_admin,
        role_id=role.id,
        is_verified=True,
    )
    office_a = Employee(
        name="OfficeA",
        email=OFFICE_A_EMAIL,
        password_hash=hash_password(PASSWORD),
        user_type=UserTypes.office_admin,
        role_id=role.id,
        company_id=company_a.id,
        is_verified=True,
    )
    office_b = Employee(
        name="OfficeB",
        email=OFFICE_B_EMAIL,
        password_hash=hash_password(PASSWORD),
        user_type=UserTypes.office_admin,
        role_id=role.id,
        company_id=company_b.id,
        is_verified=True,
    )
    db_session.add_all([super_admin, office_a, office_b])
    db_session.commit()
    db_session.refresh(super_admin)
    db_session.refresh(office_a)
    db_session.refresh(office_b)

    return {
        "role": role,
        "company_a": company_a,
        "company_b": company_b,
        "super": super_admin,
        "office_a": office_a,
        "office_b": office_b,
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
# 1. POST /auth/employees now routes through the safe path
# ---------------------------------------------------------------------------

def test_auth_employees_forces_office_admin_company_id(client, stack):
    """office_admin tries to create an employee in company B; the actor's
    company_id (A) is force-stamped regardless of what the body says."""
    token = _login(client, OFFICE_A_EMAIL)
    r = client.post(
        "/auth/employees",
        json={
            "name": "Sneaky",
            "user_type": "employee",
            "email": "sneaky-p1@example.com",
            "role_id": stack["role"].id,
            "company_id": stack["company_b"].id,  # attempt cross-tenant
        },
        headers=_auth(token),
    )
    assert r.status_code == 200, r.text

    # Confirm the employee actually landed in company_a (force-stamped),
    # not the requested company_b.
    from app.models.employee import Employee
    created = client.app.dependency_overrides
    # Use the test session via the client fixture's dependency
    # — but simpler: re-query through GET /employees.
    list_r = client.get("/employees/", headers=_auth(token))
    assert list_r.status_code == 200
    found = [
        e for e in list_r.json()["data"]["items"]
        if e["email"] == "sneaky-p1@example.com"
    ]
    assert len(found) == 1
    assert found[0]["company_id"] == stack["company_a"].id


def test_auth_employees_office_admin_cannot_create_admin(client, stack):
    """office_admin cannot escalate by creating another office_admin."""
    token = _login(client, OFFICE_A_EMAIL)
    r = client.post(
        "/auth/employees",
        json={
            "name": "Escalator",
            "user_type": "office_admin",
            "email": "escalator-p1@example.com",
            "role_id": stack["role"].id,
            "company_id": stack["company_a"].id,
        },
        headers=_auth(token),
    )
    assert r.status_code == 403


def test_auth_employees_anonymous_is_rejected(client, stack):
    """No token → 401, not 403."""
    r = client.post(
        "/auth/employees",
        json={
            "name": "Anon",
            "user_type": "employee",
            "email": "anon-p1@example.com",
            "role_id": stack["role"].id,
        },
    )
    assert r.status_code == 401


# ---------------------------------------------------------------------------
# 2 + 3. /companies/ mutations are super_admin-only; reads are tenant-scoped
# ---------------------------------------------------------------------------

def test_office_admin_cannot_create_company(client, stack):
    token = _login(client, OFFICE_A_EMAIL)
    r = client.post(
        "/companies/",
        json={"name": "Should Not Exist"},
        headers=_auth(token),
    )
    assert r.status_code == 403


def test_office_admin_cannot_update_company(client, stack):
    token = _login(client, OFFICE_A_EMAIL)
    r = client.put(
        f"/companies/{stack['company_b'].id}",
        json={"name": "Renamed"},
        headers=_auth(token),
    )
    assert r.status_code == 403


def test_office_admin_cannot_delete_company(client, stack):
    token = _login(client, OFFICE_A_EMAIL)
    r = client.delete(
        f"/companies/{stack['company_b'].id}", headers=_auth(token)
    )
    assert r.status_code == 403


def test_super_admin_can_create_company(client, stack):
    token = _login(client, SUPER_EMAIL)
    r = client.post(
        "/companies/",
        json={"name": "SA-created Co"},
        headers=_auth(token),
    )
    assert r.status_code == 200, r.text
    assert r.json()["data"]["name"] == "SA-created Co"


def test_office_admin_list_shows_only_own_company(client, stack):
    token = _login(client, OFFICE_A_EMAIL)
    r = client.get("/companies/", headers=_auth(token))
    assert r.status_code == 200, r.text
    names = {c["name"] for c in r.json()["data"]}
    assert names == {"Acme P1"}  # never sees OtherCo P1


def test_super_admin_list_shows_all_companies(client, stack):
    token = _login(client, SUPER_EMAIL)
    r = client.get("/companies/", headers=_auth(token))
    assert r.status_code == 200, r.text
    names = {c["name"] for c in r.json()["data"]}
    assert {"Acme P1", "OtherCo P1"} <= names


def test_office_admin_cannot_read_other_company(client, stack):
    """Cross-tenant GET returns 404, not 403 — hides existence."""
    token = _login(client, OFFICE_A_EMAIL)
    r = client.get(
        f"/companies/{stack['company_b'].id}", headers=_auth(token)
    )
    assert r.status_code == 404


# ---------------------------------------------------------------------------
# 4. /auth/logout returns 200 (stub — no server-side revocation today)
# ---------------------------------------------------------------------------

def test_logout_returns_200_for_authenticated_caller(client, stack):
    token = _login(client, OFFICE_A_EMAIL)
    r = client.post("/auth/logout", headers=_auth(token))
    assert r.status_code == 200, r.text
    assert "discard" in r.json()["message"].lower()


def test_logout_requires_auth(client, stack):
    r = client.post("/auth/logout")
    assert r.status_code == 401


# ---------------------------------------------------------------------------
# 5. POST /attendance/manual/{employee_id} — date in body
# ---------------------------------------------------------------------------

def test_manual_attendance_uses_path_id_and_body_date(client, stack, db_session):
    """Adds an employee in company_a, then admin marks manual attendance
    for them via the new path-based + body-date shape."""
    # Seed an employee in company_a.
    emp = Employee(
        name="Manual Target",
        email="manual-target-p1@example.com",
        password_hash=hash_password(PASSWORD),
        user_type=UserTypes.employee,
        role_id=stack["role"].id,
        company_id=stack["company_a"].id,
        is_verified=True,
    )
    db_session.add(emp)
    db_session.commit()
    db_session.refresh(emp)

    token = _login(client, OFFICE_A_EMAIL)
    r = client.post(
        f"/attendance/manual/{emp.id}",
        json={
            "date": "2026-05-15",
            "check_in": "2026-05-15T09:00:00",
            "check_out": "2026-05-15T18:00:00",
            "reason": "Forgot to clock in",
        },
        headers=_auth(token),
    )
    assert r.status_code == 200, r.text
    assert r.json()["data"]["employee_id"] == emp.id
    assert r.json()["data"]["is_manual"] is True


def test_manual_attendance_cross_tenant_is_blocked(client, stack, db_session):
    """office_admin in company A tries to mark attendance for an employee
    in company B. assert_can_access_employee blocks it at the router."""
    emp_b = Employee(
        name="OtherCo Emp",
        email="otherco-emp-p1@example.com",
        password_hash=hash_password(PASSWORD),
        user_type=UserTypes.employee,
        role_id=stack["role"].id,
        company_id=stack["company_b"].id,
        is_verified=True,
    )
    db_session.add(emp_b)
    db_session.commit()
    db_session.refresh(emp_b)

    token = _login(client, OFFICE_A_EMAIL)
    r = client.post(
        f"/attendance/manual/{emp_b.id}",
        json={
            "date": "2026-05-15",
            "check_in": "2026-05-15T09:00:00",
            "reason": "test",
        },
        headers=_auth(token),
    )
    assert r.status_code == 403
