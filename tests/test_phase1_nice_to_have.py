"""Tests for the Phase 1 "nice-to-have" stabilization work
(API_AUDIT.md section 6 #14 + section 7 audit gaps + section 8
verification items).

Covers:
  - audit log coverage extension (company CUD, attendance update/delete,
    holiday CUD, leave_balance.adjust)
  - GET /audit-logs/entities/{type}/{id} convenience URL
  - DELETE /company-holidays/bulk (both `ids` and `year` modes)
  - JWT expiry returns 401
  - soft-deleted user cannot log in
"""
from datetime import date, datetime, timedelta, timezone

import pytest
from jose import jwt

from app.core.config import settings
from app.models.audit_log import AuditLog
from app.models.attendance import Attendance, AttendanceStatus
from app.models.company import Company
from app.models.employee import Employee, UserTypes
from app.models.holiday import CompanyHoliday
from app.models.leave import LeavePolicy, LeaveType
from app.models.role import Role
from app.utils.hash import hash_password


SUPER_EMAIL = "p1nh-super@example.com"
ADMIN_EMAIL = "p1nh-admin@example.com"
EMP_EMAIL = "p1nh-emp@example.com"
EMP_ROLL = "P1NH-EMP-001"
PASSWORD = "TestPass123!"


@pytest.fixture()
def stack(db_session):
    role = Role(role_name="DefaultRole")
    db_session.add(role)
    db_session.commit()
    db_session.refresh(role)

    company_a = Company(name="Acme P1NH")
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
        name="Emp",
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


def _login(client, email=ADMIN_EMAIL) -> str:
    r = client.post(
        "/auth/admin/login", json={"email": email, "password": PASSWORD}
    )
    assert r.status_code == 200, r.text
    return r.json()["data"]["access_token"]


def _auth(token: str) -> dict:
    return {"Authorization": f"Bearer {token}"}


# ---------------------------------------------------------------------------
# Audit coverage extension
# ---------------------------------------------------------------------------

def test_company_create_emits_audit(client, stack, db_session):
    token = _login(client, SUPER_EMAIL)
    r = client.post(
        "/companies/",
        json={"name": "Audit Test Co"},
        headers=_auth(token),
    )
    assert r.status_code == 200, r.text
    new_id = r.json()["data"]["id"]

    log = (
        db_session.query(AuditLog)
        .filter(
            AuditLog.action == "company.create",
            AuditLog.entity_id == new_id,
        )
        .one()
    )
    assert log.actor_email == SUPER_EMAIL
    assert log.after["name"] == "Audit Test Co"


def test_holiday_create_emits_audit(client, stack, db_session):
    token = _login(client)
    r = client.post(
        "/company-holidays/",
        json={
            "company_id": stack["company_a"].id,
            "date": "2026-12-25",
            "name": "Christmas",
        },
        headers=_auth(token),
    )
    assert r.status_code == 200, r.text
    holiday_id = r.json()["data"]["id"]

    log = (
        db_session.query(AuditLog)
        .filter(
            AuditLog.action == "holiday.create",
            AuditLog.entity_id == holiday_id,
        )
        .one()
    )
    assert log.company_id == stack["company_a"].id
    assert log.after["name"] == "Christmas"


def test_attendance_delete_emits_audit(client, stack, db_session):
    """Soft-deleting an attendance row writes a delete audit."""
    att = Attendance(
        employee_id=stack["employee"].id,
        company_id=stack["company_a"].id,
        date=date(2026, 5, 1),
        attendance_status=AttendanceStatus.present,
        working_hours=8,
    )
    db_session.add(att)
    db_session.commit()
    db_session.refresh(att)
    att_id = att.id

    token = _login(client)
    r = client.delete(
        f"/attendance/{att_id}", headers=_auth(token)
    )
    assert r.status_code == 200, r.text

    log = (
        db_session.query(AuditLog)
        .filter(
            AuditLog.action == "attendance.delete",
            AuditLog.entity_id == att_id,
        )
        .one()
    )
    assert log.company_id == stack["company_a"].id
    assert log.before is not None


def test_leave_balance_adjust_emits_audit_with_reason(client, stack, db_session):
    """The adjustment reason is captured inside the after payload's
    _adjustment dict — auditors can read the why without a separate
    table."""
    db_session.add(LeavePolicy(
        company_id=stack["company_a"].id,
        leave_type=LeaveType.casual,
        annual_entitlement=10.0,
    ))
    db_session.commit()

    token = _login(client)
    r = client.post(
        f"/leave-balances/{stack['employee'].id}/adjust",
        json={
            "year": 2026,
            "leave_type": "casual",
            "delta": 2.0,
            "reason": "Mid-year joiner pro-rate",
        },
        headers=_auth(token),
    )
    assert r.status_code == 200, r.text

    log = (
        db_session.query(AuditLog)
        .filter(AuditLog.action == "leave_balance.adjust")
        .order_by(AuditLog.id.desc())
        .first()
    )
    assert log is not None
    adj = log.after.get("_adjustment")
    assert adj is not None
    assert adj["delta"] == 2.0
    assert adj["reason"] == "Mid-year joiner pro-rate"


# ---------------------------------------------------------------------------
# Audit-by-entity convenience URL
# ---------------------------------------------------------------------------

def test_audit_logs_entities_url_returns_only_that_entity(client, stack, db_session):
    db_session.add_all([
        AuditLog(
            actor_id=stack["admin"].id, actor_email=ADMIN_EMAIL,
            action="leave.approve", entity_type="leave", entity_id=11,
            company_id=stack["company_a"].id,
        ),
        AuditLog(
            actor_id=stack["admin"].id, actor_email=ADMIN_EMAIL,
            action="leave.reject", entity_type="leave", entity_id=11,
            company_id=stack["company_a"].id,
        ),
        AuditLog(
            actor_id=stack["admin"].id, actor_email=ADMIN_EMAIL,
            action="leave.delete", entity_type="leave", entity_id=22,
            company_id=stack["company_a"].id,
        ),
    ])
    db_session.commit()

    token = _login(client)
    r = client.get(
        "/audit-logs/entities/leave/11", headers=_auth(token)
    )
    assert r.status_code == 200, r.text
    body = r.json()["data"]
    actions = {item["action"] for item in body["items"]}
    assert actions == {"leave.approve", "leave.reject"}
    # leave 22's row is filtered out.


# ---------------------------------------------------------------------------
# Bulk holiday DELETE
# ---------------------------------------------------------------------------

def test_bulk_delete_holidays_by_ids(client, stack, db_session):
    h1 = CompanyHoliday(
        company_id=stack["company_a"].id, date=date(2026, 1, 26), name="RD",
    )
    h2 = CompanyHoliday(
        company_id=stack["company_a"].id, date=date(2026, 8, 15), name="ID",
    )
    db_session.add_all([h1, h2])
    db_session.commit()
    db_session.refresh(h1)
    db_session.refresh(h2)

    token = _login(client)
    r = client.request(
        "DELETE", "/company-holidays/bulk",
        json={
            "company_id": stack["company_a"].id,
            "ids": [h1.id, h2.id],
        },
        headers=_auth(token),
    )
    assert r.status_code == 200, r.text
    assert r.json()["data"]["deleted"] == 2
    assert r.json()["data"]["skipped"] == []


def test_bulk_delete_holidays_by_year(client, stack, db_session):
    db_session.add_all([
        CompanyHoliday(
            company_id=stack["company_a"].id,
            date=date(2026, 1, 26), name="RD-2026",
        ),
        CompanyHoliday(
            company_id=stack["company_a"].id,
            date=date(2026, 8, 15), name="ID-2026",
        ),
        # Different year — must NOT be touched.
        CompanyHoliday(
            company_id=stack["company_a"].id,
            date=date(2025, 1, 26), name="RD-2025",
        ),
    ])
    db_session.commit()

    token = _login(client)
    r = client.request(
        "DELETE", "/company-holidays/bulk",
        json={"company_id": stack["company_a"].id, "year": 2026},
        headers=_auth(token),
    )
    assert r.status_code == 200, r.text
    assert r.json()["data"]["deleted"] == 2

    # The 2025 holiday should still be listed.
    r = client.get(
        f"/company-holidays/?company_id={stack['company_a'].id}",
        headers=_auth(token),
    )
    assert r.status_code == 200
    remaining = {h["name"] for h in r.json()["data"]}
    assert remaining == {"RD-2025"}


def test_bulk_delete_requires_exactly_one_mode(client, stack):
    token = _login(client)
    # Both ids and year provided → 400.
    r = client.request(
        "DELETE", "/company-holidays/bulk",
        json={
            "company_id": stack["company_a"].id,
            "ids": [1],
            "year": 2026,
        },
        headers=_auth(token),
    )
    assert r.status_code == 400

    # Neither → 400.
    r = client.request(
        "DELETE", "/company-holidays/bulk",
        json={"company_id": stack["company_a"].id},
        headers=_auth(token),
    )
    assert r.status_code == 400


# ---------------------------------------------------------------------------
# JWT expiry
# ---------------------------------------------------------------------------

def test_expired_jwt_returns_401(client, stack):
    """Pre-baked expired token must be rejected with 401. Closes the
    coverage gap flagged in API_AUDIT.md section 8."""
    expired = jwt.encode(
        {
            "sub": str(stack["admin"].id),
            "user_type": "office_admin",
            "exp": datetime.now(timezone.utc) - timedelta(minutes=5),
        },
        settings.SECRET_KEY,
        algorithm=settings.ALGORITHM,
    )
    r = client.get("/auth/me", headers=_auth(expired))
    assert r.status_code == 401


def test_malformed_jwt_returns_401(client, stack):
    """Garbage token rejected with 401, not 500."""
    r = client.get("/auth/me", headers=_auth("not-a-real-token"))
    assert r.status_code == 401


# ---------------------------------------------------------------------------
# Soft-deleted login
# ---------------------------------------------------------------------------

def test_soft_deleted_admin_cannot_login(client, stack, db_session):
    """A deleted_at-stamped employee fails the login lookup. Closes the
    coverage gap flagged in API_AUDIT.md section 8."""
    stack["admin"].deleted_at = datetime.now(timezone.utc)
    db_session.commit()

    r = client.post(
        "/auth/admin/login",
        json={"email": ADMIN_EMAIL, "password": PASSWORD},
    )
    # Generic 400 (invalid credentials) — same shape as wrong-password, so
    # an attacker can't tell whether the email exists in the system.
    assert r.status_code == 400


def test_soft_deleted_employee_cannot_login(client, stack, db_session):
    stack["employee"].deleted_at = datetime.now(timezone.utc)
    db_session.commit()

    r = client.post(
        "/auth/employee/login",
        json={"roll_no": EMP_ROLL, "password": PASSWORD},
    )
    assert r.status_code == 400
