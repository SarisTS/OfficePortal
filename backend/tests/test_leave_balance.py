"""End-to-end tests for the leave balance ledger.

Each test seeds an office_admin + employee in one company, optionally a
LeavePolicy, then drives the public API to exercise:

  - POST /leave refused with 400 when no policy exists for that type
  - POST /leave + GET /leave-balances/me — request doesn't debit yet
  - POST /leave/{id}/approve — debits, balance reflects
  - POST /leave/{id}/approve refused when insufficient
  - DELETE /leave/{id} on an approved leave — refunds, balance restored
  - half-day leave consumes 0.5 days
  - cross-year leave debits from start_date.year only
"""

from datetime import date, timedelta

import pytest

from app.models.company import Company
from app.models.employee import Employee, UserTypes
from app.models.leave import LeavePolicy, LeaveType
from app.models.role import Role
from app.utils.hash import hash_password


ADMIN_EMAIL = "leave-admin@example.com"
EMPLOYEE_EMAIL = "leave-emp@example.com"
EMPLOYEE_ROLL = "EMP-LV-001"
PASSWORD = "TestPass123!"


@pytest.fixture()
def stack(db_session):
    """Seed company + roles + one office_admin + one employee. No policy."""
    role = Role(role_name="Default")
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
        name="Emp",
        email=EMPLOYEE_EMAIL,
        roll_no=EMPLOYEE_ROLL,
        password_hash=hash_password(PASSWORD),
        user_type=UserTypes.employee,
        role_id=role.id,
        company_id=company.id,
        is_verified=True,
    )
    db_session.add_all([admin, employee])
    db_session.commit()
    db_session.refresh(admin)
    db_session.refresh(employee)

    return {"company": company, "admin": admin, "employee": employee}


def _admin_token(client) -> str:
    r = client.post(
        "/auth/admin/login",
        json={"email": ADMIN_EMAIL, "password": PASSWORD},
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


def _seed_policy(db_session, company_id: int, leave_type: LeaveType, days: float):
    db_session.add(
        LeavePolicy(
            company_id=company_id,
            leave_type=leave_type,
            annual_entitlement=days,
        )
    )
    db_session.commit()


# ---------------------------------------------------------------------------
# The actual tests
# ---------------------------------------------------------------------------


def test_create_leave_refused_without_policy(client, stack):
    """No policy for the leave_type → POST /leave returns 400."""
    fx = stack
    token = _employee_token(client)

    today = date.today()
    r = client.post(
        "/leave/",
        json={
            "employee_id": fx["employee"].id,
            "leave_type": "casual",
            "start_date": today.isoformat(),
            "end_date": (today + timedelta(days=2)).isoformat(),
        },
        headers=_auth(token),
    )
    assert r.status_code == 400
    assert "no leave policy" in r.json()["message"].lower()


def test_balance_reflects_approval_and_refund(client, stack, db_session):
    fx = stack
    year = date.today().year
    _seed_policy(db_session, fx["company"].id, LeaveType.casual, 5.0)

    emp_token = _employee_token(client)
    admin_token = _admin_token(client)

    today = date.today()
    end = today + timedelta(days=2)   # 3-day leave (inclusive)

    # 1. employee creates leave — should succeed
    r = client.post(
        "/leave/",
        json={
            "employee_id": fx["employee"].id,
            "leave_type": "casual",
            "start_date": today.isoformat(),
            "end_date": end.isoformat(),
        },
        headers=_auth(emp_token),
    )
    assert r.status_code == 200, r.text
    leave_id = r.json()["data"]["id"]

    # 2. /leave-balances/me — pending leave does NOT debit yet
    r = client.get(
        f"/leave-balances/me?year={year}", headers=_auth(emp_token)
    )
    assert r.status_code == 200, r.text
    casual = next(
        b for b in r.json()["data"] if b["leave_type"] == "casual"
    )
    assert casual["allocated"] == 5.0
    assert casual["used"] == 0.0
    assert casual["remaining"] == 5.0

    # 3. admin approves → balance debits 3 days
    r = client.post(
        f"/leave/{leave_id}/approve", headers=_auth(admin_token)
    )
    assert r.status_code == 200, r.text

    r = client.get(
        f"/leave-balances/me?year={year}", headers=_auth(emp_token)
    )
    casual = next(
        b for b in r.json()["data"] if b["leave_type"] == "casual"
    )
    assert casual["used"] == 3.0
    assert casual["remaining"] == 2.0

    # 4. admin deletes the approved leave → balance refunds
    r = client.delete(f"/leave/{leave_id}", headers=_auth(admin_token))
    assert r.status_code == 200, r.text

    r = client.get(
        f"/leave-balances/me?year={year}", headers=_auth(emp_token)
    )
    casual = next(
        b for b in r.json()["data"] if b["leave_type"] == "casual"
    )
    assert casual["used"] == 0.0
    assert casual["remaining"] == 5.0


def test_create_leave_refused_when_insufficient(client, stack, db_session):
    fx = stack
    _seed_policy(db_session, fx["company"].id, LeaveType.casual, 2.0)
    emp_token = _employee_token(client)

    today = date.today()
    r = client.post(
        "/leave/",
        json={
            "employee_id": fx["employee"].id,
            "leave_type": "casual",
            # 5-day leave > 2-day allocation
            "start_date": today.isoformat(),
            "end_date": (today + timedelta(days=4)).isoformat(),
        },
        headers=_auth(emp_token),
    )
    assert r.status_code == 400
    assert "insufficient" in r.json()["message"].lower()


def test_half_day_consumes_half(client, stack, db_session):
    fx = stack
    year = date.today().year
    _seed_policy(db_session, fx["company"].id, LeaveType.sick, 2.0)
    emp_token = _employee_token(client)
    admin_token = _admin_token(client)

    today = date.today()
    r = client.post(
        "/leave/",
        json={
            "employee_id": fx["employee"].id,
            "leave_type": "sick",
            "start_date": today.isoformat(),
            "end_date": today.isoformat(),
            "is_half_day": True,
        },
        headers=_auth(emp_token),
    )
    assert r.status_code == 200, r.text
    leave_id = r.json()["data"]["id"]

    r = client.post(
        f"/leave/{leave_id}/approve", headers=_auth(admin_token)
    )
    assert r.status_code == 200, r.text

    r = client.get(
        f"/leave-balances/me?year={year}", headers=_auth(emp_token)
    )
    sick = next(
        b for b in r.json()["data"] if b["leave_type"] == "sick"
    )
    assert sick["used"] == 0.5
    assert sick["remaining"] == 1.5


def test_leave_skips_company_holidays_inside_range(client, stack, db_session):
    """A 3-day leave that includes 1 company holiday debits 2 days, not 3."""
    from app.models.holiday import CompanyHoliday

    fx = stack
    _seed_policy(db_session, fx["company"].id, LeaveType.casual, 5.0)

    # Mark Mar 15 as a holiday
    db_session.add(CompanyHoliday(
        company_id=fx["company"].id,
        date=date(2026, 3, 15),
        name="Some Holiday",
    ))
    db_session.commit()

    emp_token = _employee_token(client)
    admin_token = _admin_token(client)

    # Mar 14-16: 3 calendar days, of which Mar 15 is a holiday → 2 billable
    r = client.post(
        "/leave/",
        json={
            "employee_id": fx["employee"].id,
            "leave_type": "casual",
            "start_date": "2026-03-14",
            "end_date": "2026-03-16",
        },
        headers=_auth(emp_token),
    )
    assert r.status_code == 200, r.text
    leave_id = r.json()["data"]["id"]

    r = client.post(
        f"/leave/{leave_id}/approve", headers=_auth(admin_token)
    )
    assert r.status_code == 200, r.text

    # Balance debited 2 days (the holiday wasn't charged)
    r = client.get(
        "/leave-balances/me?year=2026", headers=_auth(emp_token)
    )
    casual = next(
        b for b in r.json()["data"] if b["leave_type"] == "casual"
    )
    assert casual["used"] == 2.0
    assert casual["remaining"] == 3.0


def test_leave_entirely_within_holidays_debits_zero(client, stack, db_session):
    """If every requested day is a holiday, balance is untouched but
    the leave row still exists for audit."""
    from app.models.holiday import CompanyHoliday

    fx = stack
    _seed_policy(db_session, fx["company"].id, LeaveType.casual, 5.0)
    db_session.add_all([
        CompanyHoliday(
            company_id=fx["company"].id, date=date(2026, 4, d),
            name=f"Hol {d}",
        )
        for d in (10, 11, 12)
    ])
    db_session.commit()

    emp_token = _employee_token(client)
    admin_token = _admin_token(client)

    r = client.post(
        "/leave/",
        json={
            "employee_id": fx["employee"].id,
            "leave_type": "casual",
            "start_date": "2026-04-10",
            "end_date": "2026-04-12",
        },
        headers=_auth(emp_token),
    )
    assert r.status_code == 200, r.text
    leave_id = r.json()["data"]["id"]

    r = client.post(
        f"/leave/{leave_id}/approve", headers=_auth(admin_token)
    )
    assert r.status_code == 200, r.text

    # All 3 days were holidays → 0 debited
    r = client.get(
        "/leave-balances/me?year=2026", headers=_auth(emp_token)
    )
    casual = next(
        b for b in r.json()["data"] if b["leave_type"] == "casual"
    )
    assert casual["used"] == 0.0
    assert casual["remaining"] == 5.0


def test_half_day_leave_ignores_holidays(client, stack, db_session):
    """Half-day leaves are always 0.5 — the holiday short-circuit in
    billable_leave_days kicks in before the holiday lookup."""
    from app.models.holiday import CompanyHoliday

    fx = stack
    _seed_policy(db_session, fx["company"].id, LeaveType.sick, 5.0)
    db_session.add(CompanyHoliday(
        company_id=fx["company"].id, date=date(2026, 5, 1),
        name="May Day",
    ))
    db_session.commit()

    emp_token = _employee_token(client)
    admin_token = _admin_token(client)

    r = client.post(
        "/leave/",
        json={
            "employee_id": fx["employee"].id,
            "leave_type": "sick",
            "start_date": "2026-05-01",
            "end_date": "2026-05-01",
            "is_half_day": True,
        },
        headers=_auth(emp_token),
    )
    assert r.status_code == 200, r.text
    leave_id = r.json()["data"]["id"]

    r = client.post(
        f"/leave/{leave_id}/approve", headers=_auth(admin_token)
    )
    assert r.status_code == 200, r.text

    r = client.get(
        "/leave-balances/me?year=2026", headers=_auth(emp_token)
    )
    sick = next(b for b in r.json()["data"] if b["leave_type"] == "sick")
    assert sick["used"] == 0.5  # half-day, not 0


def test_leave_skips_weekly_off_days(client, stack, db_session):
    """A leave spanning a Sunday in a company that declares Sunday as a
    weekly-off doesn't debit that day."""
    from app.models.holiday import CompanyWeeklyOff

    fx = stack
    _seed_policy(db_session, fx["company"].id, LeaveType.casual, 10.0)

    # Sunday = 6 in Python's date.weekday()
    db_session.add(CompanyWeeklyOff(
        company_id=fx["company"].id, day_of_week=6,
    ))
    db_session.commit()

    emp_token = _employee_token(client)
    admin_token = _admin_token(client)

    # Mar 13-15, 2026 — Mar 15 is a Sunday. 3 calendar days, 1 is a
    # weekly-off → 2 billable days.
    r = client.post(
        "/leave/",
        json={
            "employee_id": fx["employee"].id,
            "leave_type": "casual",
            "start_date": "2026-03-13",
            "end_date": "2026-03-15",
        },
        headers=_auth(emp_token),
    )
    assert r.status_code == 200, r.text
    leave_id = r.json()["data"]["id"]

    r = client.post(
        f"/leave/{leave_id}/approve", headers=_auth(admin_token)
    )
    assert r.status_code == 200, r.text

    r = client.get(
        "/leave-balances/me?year=2026", headers=_auth(emp_token)
    )
    casual = next(
        b for b in r.json()["data"] if b["leave_type"] == "casual"
    )
    assert casual["used"] == 2.0   # Sunday skipped
    assert casual["remaining"] == 8.0


def test_cross_year_leave_debits_only_start_year(client, stack, db_session):
    fx = stack
    _seed_policy(db_session, fx["company"].id, LeaveType.earned, 10.0)
    emp_token = _employee_token(client)
    admin_token = _admin_token(client)

    # Dec 28 → Jan 3 = 7 calendar days spanning two years
    start = date(2026, 12, 28)
    end = date(2027, 1, 3)
    r = client.post(
        "/leave/",
        json={
            "employee_id": fx["employee"].id,
            "leave_type": "earned",
            "start_date": start.isoformat(),
            "end_date": end.isoformat(),
        },
        headers=_auth(emp_token),
    )
    assert r.status_code == 200, r.text
    leave_id = r.json()["data"]["id"]

    r = client.post(
        f"/leave/{leave_id}/approve", headers=_auth(admin_token)
    )
    assert r.status_code == 200, r.text

    # start_date.year = 2026 should be debited 7 days
    r = client.get(
        "/leave-balances/me?year=2026", headers=_auth(emp_token)
    )
    earned_2026 = next(
        b for b in r.json()["data"] if b["leave_type"] == "earned"
    )
    assert earned_2026["used"] == 7.0

    # 2027 should be untouched
    r = client.get(
        "/leave-balances/me?year=2027", headers=_auth(emp_token)
    )
    earned_2027 = next(
        b for b in r.json()["data"] if b["leave_type"] == "earned"
    )
    assert earned_2027["used"] == 0.0
