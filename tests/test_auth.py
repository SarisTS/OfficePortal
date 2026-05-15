"""Smoke tests for the auth flow.

Seeds a super_admin into the in-memory test DB, logs in via
POST /auth/admin/login, then exercises GET /auth/me to verify the response
never includes password_hash / google_id.
"""

import pytest

from app.models.employee import Employee, UserTypes
from app.models.role import Role
from app.utils.hash import hash_password


ADMIN_EMAIL = "smoke-admin@example.com"
ADMIN_PASSWORD = "TestPass123!"


@pytest.fixture()
def seeded_admin(db_session):
    """Insert a Super Admin role + Employee into the test DB."""
    role = Role(role_name="Super Admin")
    db_session.add(role)
    db_session.commit()
    db_session.refresh(role)

    admin = Employee(
        name="Smoke Admin",
        email=ADMIN_EMAIL,
        password_hash=hash_password(ADMIN_PASSWORD),
        user_type=UserTypes.super_admin,
        role_id=role.id,
        is_verified=True,
    )
    db_session.add(admin)
    db_session.commit()
    db_session.refresh(admin)
    return admin


def test_admin_login_returns_token(client, seeded_admin):
    r = client.post(
        "/auth/admin/login",
        json={"email": ADMIN_EMAIL, "password": ADMIN_PASSWORD},
    )
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["status"] == 200
    assert "access_token" in body["data"]
    assert body["data"]["token_type"] == "bearer"


def test_admin_login_wrong_password_rejects(client, seeded_admin):
    r = client.post(
        "/auth/admin/login",
        json={"email": ADMIN_EMAIL, "password": "not-the-password"},
    )
    assert r.status_code == 400


def test_admin_login_extra_field_rejected(client, seeded_admin):
    """Phase 5 extra='forbid' should turn unknown fields into 422."""
    r = client.post(
        "/auth/admin/login",
        json={
            "email": ADMIN_EMAIL,
            "password": ADMIN_PASSWORD,
            "remember_me_pls": True,  # not in LoginRequest
        },
    )
    assert r.status_code == 422


def test_me_never_leaks_password_hash(client, seeded_admin):
    """Phase 1: GET /auth/me must return a sanitized profile."""
    login = client.post(
        "/auth/admin/login",
        json={"email": ADMIN_EMAIL, "password": ADMIN_PASSWORD},
    )
    token = login.json()["data"]["access_token"]

    r = client.get("/auth/me", headers={"Authorization": f"Bearer {token}"})
    assert r.status_code == 200, r.text
    body = r.json()

    profile = body["data"]
    # Sanity: the profile is the expected admin
    assert profile["email"] == ADMIN_EMAIL
    assert profile["user_type"] == UserTypes.super_admin.value
    # The two fields that used to leak — must be gone
    assert "password_hash" not in profile
    assert "google_id" not in profile


def test_me_without_token_is_401(client, seeded_admin):
    r = client.get("/auth/me")
    # FastAPI's OAuth2PasswordBearer returns 401 when no token is present.
    assert r.status_code == 401
