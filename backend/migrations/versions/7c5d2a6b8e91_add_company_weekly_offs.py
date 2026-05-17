"""add company_weekly_offs table

Revision ID: 7c5d2a6b8e91
Revises: 6b4e1f8a9c23
Create Date: 2026-05-16

Adds the recurring weekly-off pattern alongside the existing
date-based CompanyHoliday table. One row per (company_id, day_of_week)
where day_of_week follows Python's `date.weekday()` (0=Monday,
6=Sunday).

Additive, no existing tables touched, fully reversible.
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = "7c5d2a6b8e91"
down_revision: Union[str, Sequence[str], None] = "6b4e1f8a9c23"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "company_weekly_offs",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("company_id", sa.Integer(), nullable=False),
        sa.Column("day_of_week", sa.Integer(), nullable=False),
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
            "company_id", "day_of_week", name="uq_company_weekly_off"
        ),
        sa.CheckConstraint(
            "day_of_week >= 0 AND day_of_week <= 6",
            name="check_weekly_off_day_of_week",
        ),
    )
    op.create_index(
        "ix_company_weekly_offs_company_id",
        "company_weekly_offs",
        ["company_id"],
    )


def downgrade() -> None:
    op.drop_index(
        "ix_company_weekly_offs_company_id",
        table_name="company_weekly_offs",
    )
    op.drop_table("company_weekly_offs")
