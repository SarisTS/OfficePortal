"""add audit_logs table

Revision ID: 8d6e3b7c0a45
Revises: 7c5d2a6b8e91
Create Date: 2026-05-16

Adds the audit_logs table backing the compliance-critical audit trail
(employee CUD, leave approve/reject/delete, payslip generate, salary
structure CUD). The two composite indexes mirror the read patterns the
router serves: "everything for entity X" and "everything in company Y
ordered by time".

`before` and `after` are JSON to keep snapshots portable across
SQLite (tests) and Postgres (prod — JSONB-equivalent storage).

Additive, no existing tables touched, fully reversible.
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = "8d6e3b7c0a45"
down_revision: Union[str, Sequence[str], None] = "7c5d2a6b8e91"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "audit_logs",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("actor_id", sa.Integer(), nullable=True),
        sa.Column("actor_email", sa.String(length=255), nullable=True),
        sa.Column("action", sa.String(length=64), nullable=False),
        sa.Column("entity_type", sa.String(length=64), nullable=False),
        sa.Column("entity_id", sa.Integer(), nullable=True),
        sa.Column("company_id", sa.Integer(), nullable=True),
        sa.Column("before", sa.JSON(), nullable=True),
        sa.Column("after", sa.JSON(), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("NOW()"),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(["actor_id"], ["employees.id"]),
        sa.ForeignKeyConstraint(["company_id"], ["companies.id"]),
    )
    op.create_index(
        "ix_audit_logs_actor_id", "audit_logs", ["actor_id"]
    )
    op.create_index(
        "ix_audit_logs_company_id", "audit_logs", ["company_id"]
    )
    op.create_index(
        "ix_audit_logs_created_at", "audit_logs", ["created_at"]
    )
    op.create_index(
        "ix_audit_logs_entity", "audit_logs", ["entity_type", "entity_id"]
    )
    op.create_index(
        "ix_audit_logs_company_created",
        "audit_logs",
        ["company_id", "created_at"],
    )


def downgrade() -> None:
    op.drop_index("ix_audit_logs_company_created", table_name="audit_logs")
    op.drop_index("ix_audit_logs_entity", table_name="audit_logs")
    op.drop_index("ix_audit_logs_created_at", table_name="audit_logs")
    op.drop_index("ix_audit_logs_company_id", table_name="audit_logs")
    op.drop_index("ix_audit_logs_actor_id", table_name="audit_logs")
    op.drop_table("audit_logs")
