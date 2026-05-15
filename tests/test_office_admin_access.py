"""Regression tests for the office_admin RBAC expansion (Task #18).

Verifies the new behavior introduced post-merge:

  - office_admin can list / fetch shifts in their OWN company
  - office_admin gets 403 when querying shifts in ANOTHER company
  - office_admin can list the food items catalog (was super_admin-only)
  - super_admin retains unscoped global access
"""

import pytest

from app.models.company import Company
from app.models.attendance import Shift
from app.models.employee import Employee, UserTypes
from app.models.food import FoodItem
from app.models.role import Role
from app.utils.hash import hash_password


SUPER_EMAIL = "super@example.com"
OFFICE_A_EMAIL = "office-a@example.com"
OFFICE_B_EMAIL = "office-b@example.com"
PASSWORD = "TestPass123!"


@pytest.fixture()
def two_companies_and_admins(db_session):
    """Seed companies A & B, a super_admin, plus an office_admin per company."""
    role = Role(role_name="Admin")
    db_session.add(role)
    db_session.commit()
    db_session.refresh(role)

    company_a = Company(name="Company A")
    company_b = Company(name="Company B")
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

    # One shift per company so list/scope is observable.
    from datetime import time
    shift_a = Shift(
        name="Day-A", start_time=time(9, 0), end_time=time(18, 0),
        company_id=company_a.id, grace_minutes=10,
    )
    shift_b = Shift(
        name="Day-B", start_time=time(9, 0), end_time=time(18, 0),
        company_id=company_b.id, grace_minutes=10,
    )
    db_session.add_all([shift_a, shift_b])
    db_session.commit()
    db_session.refresh(shift_a)
    db_session.refresh(shift_b)

    return {
        "company_a": company_a,
        "company_b": company_b,
        "super_admin": super_admin,
        "office_a": office_a,
        "office_b": office_b,
        "shift_a": shift_a,
        "shift_b": shift_b,
    }


def _login(client, email):
    r = client.post("/auth/admin/login", json={"email": email, "password": PASSWORD})
    assert r.status_code == 200, r.text
    return r.json()["data"]["access_token"]


def _auth(token):
    return {"Authorization": f"Bearer {token}"}


def test_office_admin_lists_only_own_company_shifts(client, two_companies_and_admins):
    fx = two_companies_and_admins
    token = _login(client, OFFICE_A_EMAIL)

    r = client.get("/shifts/", headers=_auth(token))
    assert r.status_code == 200, r.text
    items = r.json()["data"]["items"]
    company_ids = {item["company_id"] for item in items}
    assert company_ids == {fx["company_a"].id}
    # Make sure the other company's shift is not present.
    shift_ids = {item["id"] for item in items}
    assert fx["shift_b"].id not in shift_ids


def test_super_admin_sees_all_shifts(client, two_companies_and_admins):
    fx = two_companies_and_admins
    token = _login(client, SUPER_EMAIL)

    r = client.get("/shifts/", headers=_auth(token))
    assert r.status_code == 200, r.text
    items = r.json()["data"]["items"]
    company_ids = {item["company_id"] for item in items}
    assert {fx["company_a"].id, fx["company_b"].id}.issubset(company_ids)


def test_office_admin_cannot_query_another_companys_shifts(
    client, two_companies_and_admins
):
    fx = two_companies_and_admins
    token = _login(client, OFFICE_A_EMAIL)

    r = client.get(
        f"/shifts/company/{fx['company_b'].id}", headers=_auth(token)
    )
    assert r.status_code == 403


def test_office_admin_cannot_fetch_another_companys_shift_by_id(
    client, two_companies_and_admins
):
    fx = two_companies_and_admins
    token = _login(client, OFFICE_A_EMAIL)

    r = client.get(f"/shifts/{fx['shift_b'].id}", headers=_auth(token))
    assert r.status_code == 403


def test_office_admin_can_list_food_catalog(client, two_companies_and_admins, db_session):
    """Phase 2 was super_admin-only on the food items list. Now any admin."""
    db_session.add(FoodItem(name="Idli", category="BREAKFAST"))
    db_session.commit()

    token = _login(client, OFFICE_A_EMAIL)
    r = client.get("/admin/food/items", headers=_auth(token))
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["total"] >= 1
    assert any(item["name"] == "Idli" for item in body["items"])
