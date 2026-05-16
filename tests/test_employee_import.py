"""Tests for POST /employees/import (bulk CSV upload)."""

from unittest.mock import patch

import pytest

from app.models.company import Company
from app.models.employee import Employee, UserTypes
from app.models.role import Role
from app.utils.hash import hash_password


ADMIN_EMAIL = "import-admin@example.com"
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
        name="Import Admin",
        email=ADMIN_EMAIL,
        password_hash=hash_password(PASSWORD),
        user_type=UserTypes.office_admin,
        role_id=role.id,
        company_id=company_a.id,
        is_verified=True,
    )
    db_session.add(admin)
    db_session.commit()
    db_session.refresh(admin)

    return {
        "admin": admin,
        "role": role,
        "company_a": company_a,
        "company_b": company_b,
    }


def _login(client) -> str:
    r = client.post(
        "/auth/admin/login", json={"email": ADMIN_EMAIL, "password": PASSWORD}
    )
    assert r.status_code == 200, r.text
    return r.json()["data"]["access_token"]


def _auth(token: str) -> dict:
    return {"Authorization": f"Bearer {token}"}


def _upload(client, token: str, csv_text: str, filename: str = "import.csv"):
    return client.post(
        "/employees/import",
        files={"file": (filename, csv_text.encode("utf-8"), "text/csv")},
        headers=_auth(token),
    )


# Welcome emails are queued via BackgroundTasks. In tests we patch the
# function so they don't actually try to dial SMTP.
@pytest.fixture(autouse=True)
def _silence_email(monkeypatch):
    monkeypatch.setattr(
        "app.crud.employee.send_employee_credentials_email",
        lambda *a, **kw: None,
    )


# ---------------------------------------------------------------------------

def test_happy_path_two_employees(client, stack):
    fx = stack
    token = _login(client)

    csv_text = (
        f"name,email,company_id,role_id,user_type\n"
        f"Alice,alice@example.com,{fx['company_a'].id},{fx['role'].id},employee\n"
        f"Bob,bob@example.com,{fx['company_a'].id},{fx['role'].id},staff\n"
    )
    r = _upload(client, token, csv_text)
    assert r.status_code == 200, r.text
    body = r.json()["data"]
    assert len(body["created"]) == 2
    assert body["skipped"] == []

    names = {e["name"] for e in body["created"]}
    assert names == {"Alice", "Bob"}


def test_mixed_valid_and_invalid_rows(client, stack):
    """A bad row doesn't abort the rest. Returns row_number for fix-up."""
    fx = stack
    token = _login(client)

    csv_text = (
        f"name,email,company_id,role_id,user_type\n"
        f"Alice,alice@example.com,{fx['company_a'].id},{fx['role'].id},employee\n"
        f"Bob,not-an-email,{fx['company_a'].id},{fx['role'].id},employee\n"
        f"Charlie,charlie@example.com,{fx['company_a'].id},{fx['role'].id},employee\n"
    )
    r = _upload(client, token, csv_text)
    assert r.status_code == 200, r.text
    body = r.json()["data"]

    # Alice (row 2) + Charlie (row 4) created. Bob (row 3) skipped.
    assert len(body["created"]) == 2
    assert {e["name"] for e in body["created"]} == {"Alice", "Charlie"}
    assert len(body["skipped"]) == 1
    assert body["skipped"][0]["row_number"] == 3


def test_office_admin_company_id_is_force_stamped(client, stack):
    """CSV trying to assign employees to another company → ignored.
    All rows land in the office_admin's own company."""
    fx = stack
    token = _login(client)

    csv_text = (
        f"name,email,company_id,role_id,user_type\n"
        f"Mallory,mallory@example.com,{fx['company_b'].id},{fx['role'].id},employee\n"
    )
    r = _upload(client, token, csv_text)
    assert r.status_code == 200, r.text
    body = r.json()["data"]
    assert len(body["created"]) == 1
    # company_id is the actor's (Acme), not company_b (OtherCo)
    assert body["created"][0]["company_id"] == fx["company_a"].id


def test_unknown_columns_are_ignored(client, stack):
    """A column the schema doesn't know about doesn't break the import.
    Without this, an admin who saved an Excel sheet with extra metadata
    columns would see all rows fail."""
    fx = stack
    token = _login(client)

    csv_text = (
        # `notes` and `extra` aren't EmployeeCreate fields
        f"name,email,company_id,role_id,user_type,notes,extra\n"
        f"Alice,alice@example.com,{fx['company_a'].id},{fx['role'].id},employee,VIP,xyz\n"
    )
    r = _upload(client, token, csv_text)
    assert r.status_code == 200, r.text
    body = r.json()["data"]
    assert len(body["created"]) == 1
    assert body["skipped"] == []


def test_duplicate_email_is_skipped(client, stack, db_session):
    """A row whose email collides with an existing employee → skipped
    with the create_employee 400 detail as the reason."""
    fx = stack
    db_session.add(Employee(
        name="Existing",
        email="taken@example.com",
        password_hash=hash_password(PASSWORD),
        user_type=UserTypes.employee,
        role_id=fx["role"].id,
        company_id=fx["company_a"].id,
        is_verified=True,
    ))
    db_session.commit()

    token = _login(client)
    csv_text = (
        f"name,email,company_id,role_id,user_type\n"
        f"Newbie,taken@example.com,{fx['company_a'].id},{fx['role'].id},employee\n"
    )
    r = _upload(client, token, csv_text)
    assert r.status_code == 200, r.text
    body = r.json()["data"]
    assert body["created"] == []
    assert len(body["skipped"]) == 1
    assert "already exists" in body["skipped"][0]["errors"][0]["detail"].lower()


def test_non_utf8_upload_returns_400(client, stack):
    fx = stack
    token = _login(client)

    # Latin-1 encoded with a byte that isn't valid UTF-8
    bad_bytes = b"name,email,company_id,role_id,user_type\nAlice,\xff,1,1,employee\n"
    r = client.post(
        "/employees/import",
        files={"file": ("bad.csv", bad_bytes, "text/csv")},
        headers=_auth(token),
    )
    assert r.status_code == 400
    assert "utf-8" in r.json()["message"].lower()
