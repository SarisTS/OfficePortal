"""add company_holidays table

Revision ID: 6b4e1f8a9c23
Revises: 5a3e9d1f7b8c
Create Date: 2026-05-16

Foundation for the holiday calendar feature. One new table, no
existing tables touched, fully reversible.

  company_holidays   one row per (company_id, date). Admin-managed
                     date-based holiday list. Consumed in later
                     commits by leave-day counting and payroll
                     LWP exclusion.
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = "6b4e1f8a9c23"
down_revision: Union[str, Sequence[str], None] = "5a3e9d1f7b8c"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "company_holidays",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("company_id", sa.Integer(), nullable=False),
        sa.Column("date", sa.Date(), nullable=False),
        sa.Column("name", sa.String(255), nullable=False),
        # AuditMixin
        sa.Column("created_at", sa.DateTime(timezone=True),
                  server_default=sa.text("NOW()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True),
                  server_default=sa.text("NOW()"), nullable=False),
        sa.Column("deleted_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_by", sa.Integer(), nullable=True),
        sa.Column("updated_by", sa.Integer(), nullable=True),
        sa.Column("is_deleted", sa.Boolean(),
                  server_default=sa.text("false"), nullable=False),
        sa.Column("is_active", sa.Boolean(),
                  server_default=sa.text("true"), nullable=False),
        sa.ForeignKeyConstraint(["company_id"], ["companies.id"]),
        sa.UniqueConstraint(
            "company_id", "date", name="uq_company_holiday"
        ),
    )
    op.create_index(
        "ix_company_holidays_company_id",
        "company_holidays",
        ["company_id"],
    )
    op.create_index(
        "idx_company_holiday_lookup",
        "company_holidays",
        ["company_id", "date"],
    )


def downgrade() -> None:
    op.drop_index(
        "idx_company_holiday_lookup", table_name="company_holidays"
    )
    op.drop_index(
        "ix_company_holidays_company_id", table_name="company_holidays"
    )
    op.drop_table("company_holidays")
