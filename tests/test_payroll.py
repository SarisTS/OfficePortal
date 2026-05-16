"""End-to-end tests for payroll: SalaryStructure CRUD + payslip generation.

Each test seeds a company with one office_admin + one employee. Some
tests also seed a second company so we can exercise cross-company
refusal.
"""

from datetime import date

import pytest

from app.models.company import Company
from app.models.employee import Employee, UserTypes
from app.models.role import Role
from app.utils.hash import hash_password


ADMIN_EMAIL = "payroll-admin@example.com"
EMPLOYEE_EMAIL = "payroll-emp@example.com"
EMPLOYEE_ROLL = "EMP-PAY-001"
OTHER_CO_EMP_EMAIL = "other-co-emp@example.com"
PASSWORD = "TestPass123!"


@pytest.fixture()
def stack(db_session):
    role = Role(role_name="DefaultRole")
    db_session.add(role)
    db_session.commit()
    db_session.refresh(role)

    company_a = Company(name="Acme")
    company_b = Company(name="Globex")
    db_session.add_all([company_a, company_b])
    db_session.commit()
    db_session.refresh(company_a)
    db_session.refresh(company_b)

    admin = Employee(
        name="Payroll Admin",
        email=ADMIN_EMAIL,
        password_hash=hash_password(PASSWORD),
        user_type=UserTypes.office_admin,
        role_id=role.id,
        company_id=company_a.id,
        is_verified=True,
    )
    employee = Employee(
        name="Payroll Emp",
        email=EMPLOYEE_EMAIL,
        roll_no=EMPLOYEE_ROLL,
        password_hash=hash_password(PASSWORD),
        user_type=UserTypes.employee,
        role_id=role.id,
        company_id=company_a.id,
        is_verified=True,
    )
    other_co_emp = Employee(
        name="Other Co Emp",
        email=OTHER_CO_EMP_EMAIL,
        password_hash=hash_password(PASSWORD),
        user_type=UserTypes.employee,
        role_id=role.id,
        company_id=company_b.id,
        is_verified=True,
    )
    db_session.add_all([admin, employee, other_co_emp])
    db_session.commit()
    db_session.refresh(admin)
    db_session.refresh(employee)
    db_session.refresh(other_co_emp)

    return {
        "admin": admin,
        "employee": employee,
        "other_co_emp": other_co_emp,
        "company_a": company_a,
        "company_b": company_b,
    }


def _admin_token(client) -> str:
    r = client.post(
        "/auth/admin/login", json={"email": ADMIN_EMAIL, "password": PASSWORD}
    )
    assert r.status_code == 200, r.text
    return r.json()["data"]["access_token"]


def _employee_token(client) -> str:
    r = client.post(
        "/auth/employee/login",
        json={"roll_no": EMPLOYEE_ROLL, "password": PASSWORD},
    )
    assert r.status_code == 200, r.text
    return r.json()["data"]["access_token"]


def _auth(token: str) -> dict:
    return {"Authorization": f"Bearer {token}"}


def _create_structure(client, admin_token, employee_id, effective_from):
    """Default test structure: gross 50000, deductions 3700, net 46300."""
    r = client.post(
        "/salary-structures/",
        json={
            "employee_id": employee_id,
            "effective_from": effective_from.isoformat(),
            "basic": 30000,
            "hra": 15000,
            "special_allowance": 5000,
            "other_allowances": 0,
            "pf": 2000,
            "professional_tax": 200,
            "tds": 1500,
            "other_deductions": 0,
        },
        headers=_auth(admin_token),
    )
    assert r.status_code == 200, r.text
    return r.json()["data"]


# ---------------------------------------------------------------------------
# SalaryStructure CRUD
# ---------------------------------------------------------------------------

def test_admin_creates_structure_and_employee_reads_via_me_salary(client, stack):
    fx = stack
    admin_token = _admin_token(client)
    _create_structure(client, admin_token, fx["employee"].id, date(2026, 1, 1))

    emp_token = _employee_token(client)
    r = client.get("/me/salary", headers=_auth(emp_token))
    assert r.status_code == 200, r.text
    data = r.json()["data"]
    assert data["basic"] == 30000
    assert data["hra"] == 15000
    assert data["effective_from"] == "2026-01-01"


def test_me_salary_404_when_no_structure_on_file(client, stack):
    """Employee with no SalaryStructure → /me/salary returns 404 (clear
    signal to the frontend that admin hasn't set them up yet)."""
    emp_token = _employee_token(client)
    r = client.get("/me/salary", headers=_auth(emp_token))
    assert r.status_code == 404


def test_office_admin_cannot_create_structure_for_other_company(client, stack):
    fx = stack
    admin_token = _admin_token(client)
    r = client.post(
        "/salary-structures/",
        json={
            "employee_id": fx["other_co_emp"].id,
            "effective_from": "2026-01-01",
            "basic": 10000,
        },
        headers=_auth(admin_token),
    )
    assert r.status_code == 403


def test_duplicate_effective_from_refused(client, stack):
    fx = stack
    admin_token = _admin_token(client)
    _create_structure(client, admin_token, fx["employee"].id, date(2026, 1, 1))

    # Second create for the same (employee, effective_from) → 400
    r = client.post(
        "/salary-structures/",
        json={
            "employee_id": fx["employee"].id,
            "effective_from": "2026-01-01",
            "basic": 99999,
        },
        headers=_auth(admin_token),
    )
    assert r.status_code == 400


# ---------------------------------------------------------------------------
# Payslip generation
# ---------------------------------------------------------------------------

def test_generate_payslip_snapshots_structure(client, stack):
    fx = stack
    admin_token = _admin_token(client)
    _create_structure(client, admin_token, fx["employee"].id, date(2026, 1, 1))

    r = client.post(
        f"/payslips/employee/{fx['employee'].id}/generate",
        json={"year": 2026, "month": 2},
        headers=_auth(admin_token),
    )
    assert r.status_code == 200, r.text
    p = r.json()["data"]

    # Snapshotted from structure
    assert p["basic"] == 30000
    assert p["hra"] == 15000
    assert p["special_allowance"] == 5000
    assert p["pf"] == 2000
    assert p["tds"] == 1500

    # Computed
    assert p["gross"] == 50000
    assert p["total_deductions"] == 3700
    assert p["net"] == 46300

    # Feb 2026 has 28 days. days_worked == days_in_period in MVP.
    assert p["days_in_period"] == 28
    assert p["days_worked"] == 28
    assert p["days_lwp"] == 0


def test_generate_without_structure_returns_400(client, stack):
    fx = stack
    admin_token = _admin_token(client)
    r = client.post(
        f"/payslips/employee/{fx['employee'].id}/generate",
        json={"year": 2026, "month": 2},
        headers=_auth(admin_token),
    )
    assert r.status_code == 400
    assert "salary structure" in r.json()["message"].lower()


def test_generate_twice_same_period_refused(client, stack):
    fx = stack
    admin_token = _admin_token(client)
    _create_structure(client, admin_token, fx["employee"].id, date(2026, 1, 1))
    body = {"year": 2026, "month": 2}

    r1 = client.post(
        f"/payslips/employee/{fx['employee'].id}/generate",
        json=body, headers=_auth(admin_token),
    )
    assert r1.status_code == 200, r1.text

    r2 = client.post(
        f"/payslips/employee/{fx['employee'].id}/generate",
        json=body, headers=_auth(admin_token),
    )
    assert r2.status_code == 400
    assert "already exists" in r2.json()["message"].lower()


def test_office_admin_cannot_generate_for_other_company(client, stack):
    fx = stack
    admin_token = _admin_token(client)
    r = client.post(
        f"/payslips/employee/{fx['other_co_emp'].id}/generate",
        json={"year": 2026, "month": 2},
        headers=_auth(admin_token),
    )
    assert r.status_code == 403


def test_employee_self_read_returns_only_own_payslips(client, stack):
    fx = stack
    admin_token = _admin_token(client)
    _create_structure(client, admin_token, fx["employee"].id, date(2026, 1, 1))
    r = client.post(
        f"/payslips/employee/{fx['employee'].id}/generate",
        json={"year": 2026, "month": 2},
        headers=_auth(admin_token),
    )
    assert r.status_code == 200, r.text

    emp_token = _employee_token(client)
    r = client.get("/payslips/me", headers=_auth(emp_token))
    assert r.status_code == 200, r.text
    items = r.json()["data"]
    assert len(items) == 1
    assert items[0]["year"] == 2026
    assert items[0]["month"] == 2
    assert items[0]["employee_id"] == fx["employee"].id


def test_download_payslip_pdf(client, stack):
    """GET /payslips/{id}/pdf returns a real PDF byte stream that the
    caller can save. Self can download own; admin can too."""
    fx = stack
    admin_token = _admin_token(client)
    _create_structure(client, admin_token, fx["employee"].id, date(2026, 1, 1))
    r = client.post(
        f"/payslips/employee/{fx['employee'].id}/generate",
        json={"year": 2026, "month": 2},
        headers=_auth(admin_token),
    )
    assert r.status_code == 200, r.text
    payslip_id = r.json()["data"]["id"]

    # As the employee — self download
    emp_token = _employee_token(client)
    r = client.get(f"/payslips/{payslip_id}/pdf", headers=_auth(emp_token))
    assert r.status_code == 200, r.text
    assert r.headers["content-type"] == "application/pdf"
    assert r.content.startswith(b"%PDF-"), "response isn't a PDF"
    assert len(r.content) > 1000, "PDF suspiciously small"
    # Content-Disposition advertises an inline filename
    assert "payslip-2026-02.pdf" in r.headers["content-disposition"]


def test_pdf_404_for_unknown_payslip(client, stack):
    emp_token = _employee_token(client)
    r = client.get("/payslips/99999/pdf", headers=_auth(emp_token))
    assert r.status_code == 404


def test_bulk_generate_for_company(client, stack):
    """Bulk path: every staff/employee in the company gets a payslip
    (or ends up in `skipped`). office_admin is correctly excluded from
    the iteration (not a staff/employee user_type)."""
    fx = stack
    admin_token = _admin_token(client)
    _create_structure(client, admin_token, fx["employee"].id, date(2026, 1, 1))

    r = client.post(
        f"/payslips/company/{fx['company_a'].id}/generate",
        json={"year": 2026, "month": 2},
        headers=_auth(admin_token),
    )
    assert r.status_code == 200, r.text
    body = r.json()["data"]

    # One staff/employee in company_a (the admin is office_admin → excluded).
    assert len(body["generated"]) == 1
    assert body["generated"][0]["employee_id"] == fx["employee"].id
    assert body["skipped"] == []
