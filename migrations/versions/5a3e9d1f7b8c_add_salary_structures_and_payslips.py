"""add salary_structures + payslips tables

Revision ID: 5a3e9d1f7b8c
Revises: 4f2a8b3c5d09
Create Date: 2026-05-16

First half of the payroll feature. Two new tables, no existing tables
touched. Both pick up AuditMixin (created_at, updated_at, deleted_at,
created_by, updated_by, is_deleted, is_active).

  salary_structures   per-employee, effective-dated. Append-only —
                      a salary change creates a new row, never edits
                      an existing one. UNIQUE(employee_id,
                      effective_from) prevents duplicates.

  payslips            (employee, year, month) snapshots. Generated
                      from the SalaryStructure active at month-end.
                      All component values copied onto the payslip
                      row so historical payslips are immutable even
                      if the underlying structure is later edited.

After this migration lands but BEFORE commit 2 ships, the tables
exist and are reachable through admin CRUD on /salary-structures
(commit 1). Payslip generation lands in commit 2.
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = "5a3e9d1f7b8c"
down_revision: Union[str, Sequence[str], None] = "4f2a8b3c5d09"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "salary_structures",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("employee_id", sa.Integer(), nullable=False),
        sa.Column("effective_from", sa.Date(), nullable=False),
        # Earnings
        sa.Column("basic", sa.Float(), server_default="0", nullable=False),
        sa.Column("hra", sa.Float(), server_default="0", nullable=False),
        sa.Column(
            "special_allowance", sa.Float(),
            server_default="0", nullable=False,
        ),
        sa.Column(
            "other_allowances", sa.Float(),
            server_default="0", nullable=False,
        ),
        # Deductions
        sa.Column("pf", sa.Float(), server_default="0", nullable=False),
        sa.Column(
            "professional_tax", sa.Float(),
            server_default="0", nullable=False,
        ),
        sa.Column("tds", sa.Float(), server_default="0", nullable=False),
        sa.Column(
            "other_deductions", sa.Float(),
            server_default="0", nullable=False,
        ),
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
        sa.ForeignKeyConstraint(["employee_id"], ["employees.id"]),
        sa.UniqueConstraint(
            "employee_id", "effective_from", name="uq_salary_structure"
        ),
        sa.CheckConstraint(
            "basic >= 0 AND hra >= 0 AND special_allowance >= 0 AND "
            "other_allowances >= 0 AND pf >= 0 AND professional_tax >= 0 "
            "AND tds >= 0 AND other_deductions >= 0",
            name="check_salary_structure_non_negative",
        ),
    )
    op.create_index(
        "ix_salary_structures_employee_id",
        "salary_structures", ["employee_id"],
    )
    op.create_index(
        "idx_salary_structure_lookup",
        "salary_structures",
        ["employee_id", "effective_from"],
    )

    op.create_table(
        "payslips",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("employee_id", sa.Integer(), nullable=False),
        sa.Column("year", sa.Integer(), nullable=False),
        sa.Column("month", sa.Integer(), nullable=False),
        # Snapshotted earnings
        sa.Column("basic", sa.Float(), server_default="0", nullable=False),
        sa.Column("hra", sa.Float(), server_default="0", nullable=False),
        sa.Column(
            "special_allowance", sa.Float(),
            server_default="0", nullable=False,
        ),
        sa.Column(
            "other_allowances", sa.Float(),
            server_default="0", nullable=False,
        ),
        # Snapshotted deductions
        sa.Column("pf", sa.Float(), server_default="0", nullable=False),
        sa.Column(
            "professional_tax", sa.Float(),
            server_default="0", nullable=False,
        ),
        sa.Column("tds", sa.Float(), server_default="0", nullable=False),
        sa.Column(
            "other_deductions", sa.Float(),
            server_default="0", nullable=False,
        ),
        # Computed (snapshotted)
        sa.Column("gross", sa.Float(), server_default="0", nullable=False),
        sa.Column(
            "total_deductions", sa.Float(),
            server_default="0", nullable=False,
        ),
        sa.Column("net", sa.Float(), server_default="0", nullable=False),
        # Informational attendance
        sa.Column(
            "days_in_period", sa.Integer(),
            server_default="0", nullable=False,
        ),
        sa.Column(
            "days_worked", sa.Float(), server_default="0", nullable=False
        ),
        sa.Column(
            "days_lwp", sa.Float(), server_default="0", nullable=False
        ),
        sa.Column(
            "generated_at", sa.DateTime(timezone=True),
            server_default=sa.text("NOW()"), nullable=False,
        ),
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
        sa.ForeignKeyConstraint(["employee_id"], ["employees.id"]),
        sa.UniqueConstraint(
            "employee_id", "year", "month", name="uq_payslip_period"
        ),
        sa.CheckConstraint(
            "month >= 1 AND month <= 12",
            name="check_payslip_month_range",
        ),
    )
    op.create_index(
        "ix_payslips_employee_id", "payslips", ["employee_id"]
    )
    op.create_index(
        "idx_payslip_lookup", "payslips",
        ["employee_id", "year", "month"],
    )


def downgrade() -> None:
    op.drop_index("idx_payslip_lookup", table_name="payslips")
    op.drop_index("ix_payslips_employee_id", table_name="payslips")
    op.drop_table("payslips")

    op.drop_index(
        "idx_salary_structure_lookup", table_name="salary_structures"
    )
    op.drop_index(
        "ix_salary_structures_employee_id", table_name="salary_structures"
    )
    op.drop_table("salary_structures")
