"""add leave_policies + leave_balances tables

Revision ID: 4f2a8b3c5d09
Revises: 3e1d8f4a6c92
Create Date: 2026-05-16

First half of the leave-balance-tracking feature. Adds two new tables
and the indexes the lookup path needs. Additive — no existing tables
touched.

  leave_policies   one row per (company, leave_type) declaring how
                   many days are granted per year. Created by admins
                   via POST /leave-policies.

  leave_balances   one row per (employee, year, leave_type) tracking
                   `allocated` (seeded from the policy at first read)
                   and `used` (incremented on approve, decremented on
                   cancel-approved). `remaining` is a derived field
                   exposed by the response schema.

Both tables inherit AuditMixin so they pick up created_at/updated_at/
deleted_at/created_by/updated_by/is_deleted/is_active.

After this migration lands but BEFORE commit 2 ships, the new tables
exist and are empty — existing leave create/approve/delete code paths
still ignore them.
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = "4f2a8b3c5d09"
down_revision: Union[str, Sequence[str], None] = "3e1d8f4a6c92"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


# The Enum already exists from the initial migration. Don't re-create
# it; bind by name with create_type=False on both tables.
_leave_type = sa.Enum("casual", "sick", "earned", name="leavetype", create_type=False)


def upgrade() -> None:
    op.create_table(
        "leave_policies",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("company_id", sa.Integer(), nullable=False),
        sa.Column("leave_type", _leave_type, nullable=False),
        sa.Column("annual_entitlement", sa.Float(), nullable=False),
        # AuditMixin columns
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
        sa.UniqueConstraint("company_id", "leave_type", name="uq_leave_policy"),
    )
    op.create_index(
        "ix_leave_policies_company_id", "leave_policies", ["company_id"]
    )

    op.create_table(
        "leave_balances",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("employee_id", sa.Integer(), nullable=False),
        sa.Column("year", sa.Integer(), nullable=False),
        sa.Column("leave_type", _leave_type, nullable=False),
        sa.Column("allocated", sa.Float(),
                  server_default=sa.text("0"), nullable=False),
        sa.Column("used", sa.Float(),
                  server_default=sa.text("0"), nullable=False),
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
        sa.ForeignKeyConstraint(["employee_id"], ["employees.id"]),
        sa.UniqueConstraint(
            "employee_id", "year", "leave_type", name="uq_leave_balance"
        ),
    )
    op.create_index(
        "ix_leave_balances_employee_id", "leave_balances", ["employee_id"]
    )
    op.create_index(
        "idx_leave_balance_lookup",
        "leave_balances",
        ["employee_id", "year", "leave_type"],
    )


def downgrade() -> None:
    op.drop_index("idx_leave_balance_lookup", table_name="leave_balances")
    op.drop_index("ix_leave_balances_employee_id", table_name="leave_balances")
    op.drop_table("leave_balances")

    op.drop_index("ix_leave_policies_company_id", table_name="leave_policies")
    op.drop_table("leave_policies")
