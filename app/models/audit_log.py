"""Audit log for compliance-critical writes.

One row per sensitive mutation (employee CUD, leave approve/reject/delete,
payslip generate, salary structure CUD). Captures WHO did WHAT to WHICH
ROW, plus a JSON snapshot of the row before and after the change so HR /
finance auditors can answer "what was it?" without needing point-in-time
DB backups.

`actor_email` is snapshotted alongside `actor_id` because the FK is set
ON DELETE no-action and the actor row could be soft-deleted later — we
still want the audit log to remain readable.

`company_id` drives the tenant scope on read: office_admin sees only
their company's logs; super_admin is unscoped. It's nullable for the
rare system action that has no tenant (none today, but cheap to support).
"""
from sqlalchemy import (
    Column, DateTime, ForeignKey, Index, Integer, JSON, String, func,
)
from sqlalchemy.orm import relationship

from app.database.base import Base


class AuditLog(Base):
    __tablename__ = "audit_logs"

    id = Column(Integer, primary_key=True)

    actor_id = Column(
        Integer, ForeignKey("employees.id"), nullable=True, index=True
    )
    actor_email = Column(String(255), nullable=True)

    # "<entity>.<verb>" — e.g. "employee.create", "leave.approve",
    # "payslip.generate". Free-form string rather than an enum so adding
    # a new action doesn't require a migration.
    action = Column(String(64), nullable=False)

    entity_type = Column(String(64), nullable=False)
    entity_id = Column(Integer, nullable=True)

    company_id = Column(
        Integer, ForeignKey("companies.id"), nullable=True, index=True
    )

    # JSON snapshots of the row before / after. Nullable because creates
    # have no `before` and deletes have no `after`.
    before = Column(JSON, nullable=True)
    after = Column(JSON, nullable=True)

    created_at = Column(
        DateTime(timezone=True),
        server_default=func.now(),
        nullable=False,
        index=True,
    )

    actor = relationship("Employee", foreign_keys=[actor_id])
    company = relationship("Company", foreign_keys=[company_id])

    __table_args__ = (
        # Hot-path read: "show me everything that happened to leave 42".
        Index("ix_audit_logs_entity", "entity_type", "entity_id"),
        # Hot-path read: "show me the last 50 events in my company".
        Index(
            "ix_audit_logs_company_created", "company_id", "created_at"
        ),
    )
