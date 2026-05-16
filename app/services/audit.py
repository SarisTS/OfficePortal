"""Audit-log writer.

`log_audit(...)` is the single entry point CRUD/service code calls when it
wants to record a compliance-critical write. The audit row is added to the
caller's session (NOT committed) so that:

  - if the caller's transaction commits → the audit row commits with it
  - if the caller's transaction rolls back → the audit row rolls back too,
    so the audit log never references actions that didn't actually happen

If building the AuditLog row itself fails (e.g. a non-JSON-serializable
value sneaks into a snapshot), we swallow the exception and log via loguru
rather than letting auditing break the user request. Missing audit is a
problem; failed user write because of audit is a worse problem.

`snapshot()` turns a SQLAlchemy model instance into a JSON-safe dict of its
column values — used by callers to build the `before` / `after` payloads.
"""
from __future__ import annotations

import enum
from datetime import date, datetime
from decimal import Decimal
from typing import Any, Mapping

from sqlalchemy import inspect
from sqlalchemy.orm import Session

from app.core.logger import get_logger
from app.models.audit_log import AuditLog

logger = get_logger()


def _jsonify(value: Any) -> Any:
    """Coerce values that the stdlib JSON encoder rejects into types it
    accepts. Conservatively scoped to types we actually see in our models —
    extend if a new column type starts surfacing."""
    if value is None or isinstance(value, (bool, int, float, str)):
        return value
    if isinstance(value, (datetime, date)):
        return value.isoformat()
    if isinstance(value, Decimal):
        return float(value)
    if isinstance(value, enum.Enum):
        return value.value
    if isinstance(value, (list, tuple)):
        return [_jsonify(v) for v in value]
    if isinstance(value, dict):
        return {k: _jsonify(v) for k, v in value.items()}
    # Fall back to repr so the audit row is never lost over an unknown
    # column type; the auditor sees a stringified value instead of nothing.
    return repr(value)


def snapshot(instance) -> dict[str, Any] | None:
    """Capture a model row's column values as a JSON-safe dict.

    Returns None for None (so callers can pass through optional fetches
    without checking). Relationships and synthetic attributes are skipped
    — only mapped columns are read, which keeps snapshots stable across
    schema changes.
    """
    if instance is None:
        return None
    mapper = inspect(instance).mapper
    return {
        col.key: _jsonify(getattr(instance, col.key))
        for col in mapper.column_attrs
    }


def log_audit(
    db: Session,
    *,
    actor,
    action: str,
    entity_type: str,
    entity_id: int | None,
    company_id: int | None = None,
    before: Mapping[str, Any] | None = None,
    after: Mapping[str, Any] | None = None,
) -> None:
    """Record an audit entry on the caller's session.

    The caller is responsible for the surrounding transaction's lifecycle
    — this function only does ``db.add(...)`` and a ``flush()`` to surface
    obvious errors (e.g. FK violation) inside the try block so they're
    swallowed instead of bubbling out of an unrelated commit later.
    """
    try:
        row = AuditLog(
            actor_id=getattr(actor, "id", None),
            actor_email=getattr(actor, "email", None),
            action=action,
            entity_type=entity_type,
            entity_id=entity_id,
            company_id=company_id,
            before=dict(before) if before is not None else None,
            after=dict(after) if after is not None else None,
        )
        db.add(row)
        db.flush()
    except Exception:
        logger.exception(
            "audit log write failed (action=%s entity=%s:%s) — swallowed",
            action, entity_type, entity_id,
        )
