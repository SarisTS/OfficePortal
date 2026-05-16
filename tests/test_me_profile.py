"""Tests for the self-service profile endpoints at /me/profile."""
import pytest

from app.models.company import Company
from app.models.employee import Employee, UserTypes
from app.models.role import Role
from app.utils.hash import hash_password


# Two seeded users so the uniqueness collision tests have something
# to collide against. Both office_admin so they can log in via the
# admin/login flow (employee/login needs a roll_no, which is admin-set
# and not in scope here).
EMAIL_A = "self-svc-a@example.com"
EMAIL_B = "self-svc-b@example.com"
MOBILE_A = "9000000001"
MOBILE_B = "9000000002"
PASSWORD = "TestPass123!"


@pytest.fixture()
def two_users(db_session):
    role = Role(role_name="DefaultRole")
    company = Company(name="Acme")
    db_session.add_all([role, company])
    db_session.commit()
    db_session.refresh(role)
    db_session.refresh(company)

    user_a = Employee(
        name="User A",
        email=EMAIL_A,
        mobile=MOBILE_A,
        password_hash=hash_password(PASSWORD),
        user_type=UserTypes.office_admin,
        role_id=role.id,
        company_id=company.id,
        is_verified=True,
    )
    user_b = Employee(
        name="User B",
        email=EMAIL_B,
        mobile=MOBILE_B,
        password_hash=hash_password(PASSWORD),
        user_type=UserTypes.office_admin,
        role_id=role.id,
        company_id=company.id,
        is_verified=True,
    )
    db_session.add_all([user_a, user_b])
    db_session.commit()
    db_session.refresh(user_a)
    db_session.refresh(user_b)

    return {"a": user_a, "b": user_b, "company": company}


def _login(client, email: str) -> str:
    r = client.post(
        "/auth/admin/login", json={"email": email, "password": PASSWORD}
    )
    assert r.status_code == 200, r.text
    return r.json()["data"]["access_token"]


def _auth(token: str) -> dict:
    return {"Authorization": f"Bearer {token}"}


# ---------------------------------------------------------------------------

def test_get_profile_returns_sanitized_data(client, two_users):
    fx = two_users
    token = _login(client, EMAIL_A)

    r = client.get("/me/profile", headers=_auth(token))
    assert r.status_code == 200, r.text
    body = r.json()["data"]

    # Identity matches the seeded user
    assert body["email"] == EMAIL_A
    assert body["mobile"] == MOBILE_A
    assert body["name"] == "User A"
    assert body["user_type"] == UserTypes.office_admin.value

    # Sensitive fields are not in the response schema → cannot leak
    assert "password_hash" not in body
    assert "google_id" not in body


def test_get_profile_without_token_is_401(client, two_users):
    r = client.get("/me/profile")
    assert r.status_code == 401


def test_put_profile_updates_allowed_fields(client, two_users):
    fx = two_users
    token = _login(client, EMAIL_A)

    r = client.put(
        "/me/profile",
        json={
            "mobile": "9111111111",
            "address_line_1": "12 New Street",
            "city": "Bangalore",
            "pincode": "560001",
        },
        headers=_auth(token),
    )
    assert r.status_code == 200, r.text
    body = r.json()["data"]
    assert body["mobile"] == "9111111111"
    assert body["address_line_1"] == "12 New Street"
    assert body["city"] == "Bangalore"
    assert body["pincode"] == "560001"

    # Fields NOT in the request stay untouched
    assert body["name"] == "User A"
    assert body["email"] == EMAIL_A


def test_put_profile_rejects_forbidden_fields(client, two_users):
    """Anything outside the ProfileUpdate allowlist returns 422 thanks
    to StrictRequestModel's extra="forbid"."""
    token = _login(client, EMAIL_A)

    for forbidden_field, value in [
        ("name", "Hacker McHackerson"),
        ("user_type", "super_admin"),
        ("role_id", 1),
        ("company_id", 99),
        ("is_verified", True),
        ("roll_no", "SMUGGLE"),
    ]:
        r = client.put(
            "/me/profile",
            json={forbidden_field: value},
            headers=_auth(token),
        )
        assert r.status_code == 422, (
            f"{forbidden_field}={value!r} should be 422, got "
            f"{r.status_code}: {r.text}"
        )


def test_put_profile_refuses_mobile_collision(client, two_users):
    """User A trying to take User B's mobile gets a friendly 400."""
    fx = two_users
    token = _login(client, EMAIL_A)

    r = client.put(
        "/me/profile",
        json={"mobile": MOBILE_B},
        headers=_auth(token),
    )
    assert r.status_code == 400
    assert "mobile" in r.json()["message"].lower()


def test_put_profile_refuses_email_collision(client, two_users):
    """Same as above for email — case-insensitive comparison."""
    token = _login(client, EMAIL_A)

    # Try B's email with mixed case to also exercise the lowercase
    # normalization on the way in.
    r = client.put(
        "/me/profile",
        json={"email": EMAIL_B.upper()},
        headers=_auth(token),
    )
    assert r.status_code == 400
    assert "email" in r.json()["message"].lower()


def test_put_profile_same_value_is_idempotent(client, two_users):
    """Submitting your own current mobile shouldn't trip the collision
    check (the WHERE filters out self via Employee.id != user.id)."""
    token = _login(client, EMAIL_A)

    r = client.put(
        "/me/profile",
        json={"mobile": MOBILE_A},
        headers=_auth(token),
    )
    assert r.status_code == 200, r.text
    assert r.json()["data"]["mobile"] == MOBILE_A
