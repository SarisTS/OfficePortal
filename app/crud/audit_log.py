"""Read-only queries for /audit-logs.

Tenant scoping is enforced here so the router stays thin:
  super_admin    → no scope filter (sees every row)
  office_admin   → company_id == actor.company_id

Optional filters: actor_id, entity_type, entity_id, action, date range.
"""
from __future__ import annotations

from datetime import date, datetime, time, timezone

from sqlalchemy.orm import Session

from app.core.permissions import is_super_admin
from app.models.audit_log import AuditLog


def list_audit_logs(
    db: Session,
    actor,
    *,
    actor_id: int | None = None,
    entity_type: str | None = None,
    entity_id: int | None = None,
    action: str | None = None,
    from_date: date | None = None,
    to_date: date | None = None,
    skip: int = 0,
    limit: int = 50,
) -> tuple[int, list[AuditLog]]:
    query = db.query(AuditLog)

    # Tenant scope. super_admin reads everything; everyone else is pinned
    # to their own company. If an office_admin has a NULL company_id
    # (shouldn't happen — defended at row creation) they see nothing,
    # which is the safe default.
    if not is_super_admin(actor):
        query = query.filter(AuditLog.company_id == actor.company_id)

    if actor_id is not None:
        query = query.filter(AuditLog.actor_id == actor_id)
    if entity_type is not None:
        query = query.filter(AuditLog.entity_type == entity_type)
    if entity_id is not None:
        query = query.filter(AuditLog.entity_id == entity_id)
    if action is not None:
        query = query.filter(AuditLog.action == action)

    # Treat from_date/to_date as calendar days in UTC. Inclusive on both
    # ends. Caller passes dates, we widen to the full day on the upper
    # bound so "to_date = 2026-05-16" includes events at 23:59:59.
    if from_date is not None:
        query = query.filter(
            AuditLog.created_at >= datetime.combine(
                from_date, time.min, tzinfo=timezone.utc,
            )
        )
    if to_date is not None:
        query = query.filter(
            AuditLog.created_at <= datetime.combine(
                to_date, time.max, tzinfo=timezone.utc,
            )
        )

    total = query.count()
    items = (
        query.order_by(AuditLog.created_at.desc(), AuditLog.id.desc())
        .offset(skip)
        .limit(limit)
        .all()
    )
    return total, items


def get_audit_log(db: Session, log_id: int, actor) -> AuditLog | None:
    """Fetch a single audit log with tenant scoping."""
    query = db.query(AuditLog).filter(AuditLog.id == log_id)
    if not is_super_admin(actor):
        query = query.filter(AuditLog.company_id == actor.company_id)
    return query.first()
