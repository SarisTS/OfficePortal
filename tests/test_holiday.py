"""Tests for company holiday calendar CRUD + /me/holidays.

Integration with leave and payroll lives in tests_leave_balance.py and
tests/test_payroll.py respectively — those follow in commits 2 and 3.
"""
from datetime import date

import pytest

from app.models.company import Company
from app.models.employee import Employee, UserTypes
from app.models.holiday import CompanyHoliday
from app.models.role import Role
from app.utils.hash import hash_password


ADMIN_EMAIL = "holiday-admin@example.com"
OTHER_ADMIN_EMAIL = "other-co-admin@example.com"
EMP_EMAIL = "holiday-emp@example.com"
EMP_ROLL = "EMP-HOL-001"
PASSWORD = "TestPass123!"


@pytest.fixture()
def stack(db_session):
    role = Role(role_name="DefaultRole")
    db_session.add(role)
    db_session.commit()
    db_session.refresh(role)

    company_a = Company(name="Acme")
    company_b = Company(name="OtherCo")
    db_session.add_all([company_a, company_b])
    db_session.commit()
    db_session.refresh(company_a)
    db_session.refresh(company_b)

    admin = Employee(
        name="Holiday Admin",
        email=ADMIN_EMAIL,
        password_hash=hash_password(PASSWORD),
        user_type=UserTypes.office_admin,
        role_id=role.id,
        company_id=company_a.id,
        is_verified=True,
    )
    other_admin = Employee(
        name="Other Admin",
        email=OTHER_ADMIN_EMAIL,
        password_hash=hash_password(PASSWORD),
        user_type=UserTypes.office_admin,
        role_id=role.id,
        company_id=company_b.id,
        is_verified=True,
    )
    employee = Employee(
        name="Employee A",
        email=EMP_EMAIL,
        roll_no=EMP_ROLL,
        password_hash=hash_password(PASSWORD),
        user_type=UserTypes.employee,
        role_id=role.id,
        company_id=company_a.id,
        is_verified=True,
    )
    db_session.add_all([admin, other_admin, employee])
    db_session.commit()
    db_session.refresh(admin)
    db_session.refresh(other_admin)
    db_session.refresh(employee)

    return {
        "admin": admin,
        "other_admin": other_admin,
        "employee": employee,
        "company_a": company_a,
        "company_b": company_b,
    }


def _login(client, email: str) -> str:
    r = client.post(
        "/auth/admin/login", json={"email": email, "password": PASSWORD}
    )
    assert r.status_code == 200, r.text
    return r.json()["data"]["access_token"]


def _employee_login(client) -> str:
    r = client.post(
        "/auth/employee/login",
        json={"roll_no": EMP_ROLL, "password": PASSWORD},
    )
    assert r.status_code == 200, r.text
    return r.json()["data"]["access_token"]


def _auth(token: str) -> dict:
    return {"Authorization": f"Bearer {token}"}


# ---------------------------------------------------------------------------

def test_admin_create_single_holiday(client, stack):
    fx = stack
    token = _login(client, ADMIN_EMAIL)

    r = client.post(
        "/company-holidays/",
        json={
            "company_id": fx["company_a"].id,
            "date": "2026-01-26",
            "name": "Republic Day",
        },
        headers=_auth(token),
    )
    assert r.status_code == 200, r.text
    data = r.json()["data"]
    assert data["date"] == "2026-01-26"
    assert data["name"] == "Republic Day"
    assert data["company_id"] == fx["company_a"].id


def test_office_admin_cannot_create_for_other_company(client, stack):
    fx = stack
    token = _login(client, ADMIN_EMAIL)
    r = client.post(
        "/company-holidays/",
        json={
            "company_id": fx["company_b"].id,
            "date": "2026-01-26",
            "name": "Smuggle",
        },
        headers=_auth(token),
    )
    assert r.status_code == 403


def test_duplicate_date_refused(client, stack):
    fx = stack
    token = _login(client, ADMIN_EMAIL)
    body = {
        "company_id": fx["company_a"].id,
        "date": "2026-08-15",
        "name": "Independence Day",
    }
    r1 = client.post(
        "/company-holidays/", json=body, headers=_auth(token)
    )
    assert r1.status_code == 200, r1.text

    r2 = client.post(
        "/company-holidays/", json=body, headers=_auth(token)
    )
    assert r2.status_code == 400


def test_bulk_create(client, stack):
    fx = stack
    token = _login(client, ADMIN_EMAIL)
    r = client.post(
        "/company-holidays/bulk",
        json={
            "company_id": fx["company_a"].id,
            "holidays": [
                {"date": "2026-01-26", "name": "Republic Day"},
                {"date": "2026-08-15", "name": "Independence Day"},
                {"date": "2026-10-02", "name": "Gandhi Jayanti"},
            ],
        },
        headers=_auth(token),
    )
    assert r.status_code == 200, r.text
    body = r.json()["data"]
    assert len(body["created"]) == 3
    assert body["skipped"] == []


def test_bulk_create_skips_existing(client, stack, db_session):
    """A duplicate inside a bulk request is skipped, not aborted."""
    fx = stack
    # Pre-seed Republic Day so the bulk request hits a duplicate
    db_session.add(CompanyHoliday(
        company_id=fx["company_a"].id,
        date=date(2026, 1, 26),
        name="Republic Day (existing)",
    ))
    db_session.commit()

    token = _login(client, ADMIN_EMAIL)
    r = client.post(
        "/company-holidays/bulk",
        json={
            "company_id": fx["company_a"].id,
            "holidays": [
                {"date": "2026-01-26", "name": "Republic Day"},   # dup
                {"date": "2026-08-15", "name": "Independence Day"},
            ],
        },
        headers=_auth(token),
    )
    assert r.status_code == 200, r.text
    body = r.json()["data"]
    assert len(body["created"]) == 1
    assert len(body["skipped"]) == 1
    assert body["skipped"][0]["date"] == "2026-01-26"


def test_list_filtered_by_year_and_month(client, stack, db_session):
    fx = stack
    db_session.add_all([
        CompanyHoliday(
            company_id=fx["company_a"].id, date=date(2026, 1, 26),
            name="Republic Day",
        ),
        CompanyHoliday(
            company_id=fx["company_a"].id, date=date(2026, 8, 15),
            name="Independence Day",
        ),
        CompanyHoliday(
            company_id=fx["company_a"].id, date=date(2027, 1, 26),
            name="Republic Day 2027",
        ),
    ])
    db_session.commit()

    token = _login(client, ADMIN_EMAIL)

    r = client.get("/company-holidays/?year=2026", headers=_auth(token))
    assert r.status_code == 200, r.text
    names = [h["name"] for h in r.json()["data"]]
    assert "Republic Day" in names
    assert "Independence Day" in names
    assert "Republic Day 2027" not in names

    r = client.get(
        "/company-holidays/?year=2026&month=1", headers=_auth(token)
    )
    names = [h["name"] for h in r.json()["data"]]
    assert names == ["Republic Day"]


def test_employee_can_list_own_holidays(client, stack, db_session):
    fx = stack
    db_session.add(CompanyHoliday(
        company_id=fx["company_a"].id, date=date(2026, 1, 26),
        name="Republic Day",
    ))
    # And one in the OTHER company that should NOT appear
    db_session.add(CompanyHoliday(
        company_id=fx["company_b"].id, date=date(2026, 1, 26),
        name="Other Co's Republic Day",
    ))
    db_session.commit()

    token = _employee_login(client)
    r = client.get("/me/holidays?year=2026", headers=_auth(token))
    assert r.status_code == 200, r.text
    items = r.json()["data"]
    assert len(items) == 1
    assert items[0]["name"] == "Republic Day"


def test_office_admin_list_scoped_to_own_company(client, stack, db_session):
    """Even if office_admin passes company_id of another company in the
    query, the handler ignores it and uses their own."""
    fx = stack
    db_session.add_all([
        CompanyHoliday(
            company_id=fx["company_a"].id, date=date(2026, 1, 1),
            name="Acme NYD",
        ),
        CompanyHoliday(
            company_id=fx["company_b"].id, date=date(2026, 1, 1),
            name="OtherCo NYD",
        ),
    ])
    db_session.commit()

    token = _login(client, ADMIN_EMAIL)
    r = client.get(
        f"/company-holidays/?company_id={fx['company_b'].id}&year=2026",
        headers=_auth(token),
    )
    assert r.status_code == 200, r.text
    names = [h["name"] for h in r.json()["data"]]
    assert names == ["Acme NYD"]  # NOT OtherCo NYD


def test_update_holiday(client, stack, db_session):
    fx = stack
    h = CompanyHoliday(
        company_id=fx["company_a"].id, date=date(2026, 1, 26),
        name="Republic Day",
    )
    db_session.add(h)
    db_session.commit()
    db_session.refresh(h)

    token = _login(client, ADMIN_EMAIL)
    r = client.put(
        f"/company-holidays/{h.id}",
        json={"name": "Republic Day (national holiday)"},
        headers=_auth(token),
    )
    assert r.status_code == 200, r.text
    assert r.json()["data"]["name"] == "Republic Day (national holiday)"


def test_delete_holiday(client, stack, db_session):
    fx = stack
    h = CompanyHoliday(
        company_id=fx["company_a"].id, date=date(2026, 1, 26),
        name="To delete",
    )
    db_session.add(h)
    db_session.commit()
    db_session.refresh(h)

    token = _login(client, ADMIN_EMAIL)
    r = client.delete(
        f"/company-holidays/{h.id}", headers=_auth(token)
    )
    assert r.status_code == 200, r.text

    # Subsequent GET returns 404 (soft-deleted)
    r = client.get(
        f"/company-holidays/{h.id}", headers=_auth(token)
    )
    assert r.status_code == 404
