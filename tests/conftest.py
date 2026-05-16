"""Pytest fixtures for HRMS backend smoke tests.

Strategy: stand up an in-memory SQLite database, create every table from
the SQLAlchemy metadata, and override the FastAPI ``get_db`` dependency
to hand sessions out of that SQLite engine. FastAPI's TestClient then
exercises real router/CRUD/service code without touching Postgres.

Caveats — what SQLite does NOT enforce that Postgres does:
  - partial unique indexes (the ``postgresql_where=...`` ones added in
    Phase 3 are silently dropped) — soft-delete uniqueness is not tested
  - server defaults written as ``sa.text("NOW()")`` work via SQLite's
    CURRENT_TIMESTAMP fallback
  - ``with_for_update()`` is a no-op on SQLite
  - native ENUM types fall back to VARCHAR + CHECK

These tests are smoke checks for wiring, not a substitute for an
integration suite against a real Postgres. The latter is a Phase 7
candidate when you want one.
"""

from __future__ import annotations

import os
import sys

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

# Make sure the app package is importable from the repo root.
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))


# ---------------------------------------------------------------------------
# Test-only SQLite engine
# ---------------------------------------------------------------------------

TEST_DATABASE_URL = "sqlite:///:memory:"

# StaticPool keeps a single shared connection so the in-memory schema
# survives between requests in the same test.
_test_engine = create_engine(
    TEST_DATABASE_URL,
    connect_args={"check_same_thread": False},
    poolclass=StaticPool,
)
TestingSessionLocal = sessionmaker(
    autocommit=False, autoflush=False, bind=_test_engine
)


@pytest.fixture(scope="session", autouse=True)
def _create_schema():
    """Build every table once at session start, drop on teardown."""
    # Import here so models register against Base before create_all runs.
    from app.database.base import Base
    import app.models  # noqa: F401 — side-effect imports all models

    Base.metadata.create_all(bind=_test_engine)
    yield
    Base.metadata.drop_all(bind=_test_engine)


@pytest.fixture()
def db_session():
    """A fresh SQLAlchemy session per test, rolled back at the end."""
    connection = _test_engine.connect()
    transaction = connection.begin()
    session = TestingSessionLocal(bind=connection)
    try:
        yield session
    finally:
        session.close()
        transaction.rollback()
        connection.close()


# POST /employees/ queues a welcome email via BackgroundTasks. In Starlette's
# TestClient, background-task exceptions propagate out of the request call, so
# any test that creates an employee will dial real SMTP unless we patch the
# sender. Local .env often has working Gmail creds; CI's .env (copied from
# .env.example) has placeholders that Google rejects with 535 BadCredentials.
# Globally silencing here keeps individual test files from having to remember.
@pytest.fixture(autouse=True)
def _silence_employee_email(monkeypatch):
    monkeypatch.setattr(
        "app.crud.employee.send_employee_credentials_email",
        lambda *a, **kw: None,
    )


@pytest.fixture()
def client(db_session):
    """FastAPI TestClient with the get_db dependency overridden.

    Yields a TestClient. Every request handled by the app inside the test
    will see the same db_session (so seed data written in the test setup
    is visible to the request).
    """
    from app.database.database import get_db
    from main import app

    def _override_get_db():
        try:
            yield db_session
        finally:
            # Session lifecycle is owned by the db_session fixture.
            pass

    app.dependency_overrides[get_db] = _override_get_db
    with TestClient(app) as tc:
        yield tc
    app.dependency_overrides.pop(get_db, None)
