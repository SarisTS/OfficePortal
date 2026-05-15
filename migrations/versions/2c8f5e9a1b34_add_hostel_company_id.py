"""add hostels.company_id for per-company scoping

Revision ID: 2c8f5e9a1b34
Revises: 1a7c4d9b2e80
Create Date: 2026-05-15

Adds the missing Hostel.company_id column so office_admin RBAC can be
expressed in the schema. Before this migration, hostels had no company
association — only a geographic location_id — so the post-Phase-2
"any admin can manage hostels" stopgap was the only thing expressible.

Strategy:
  - Add company_id as a nullable FK to companies. Existing rows stay
    valid (their company_id becomes NULL) and are treated as "legacy /
    global" by the new CRUD logic: readable by any admin, modifiable
    only by super_admin until super_admin classifies them.
  - Index company_id since the new tenant filter uses it on every
    read path.
  - The downgrade() reverses cleanly.

Optional follow-up after this lands (recommended but not done here —
data inference is risky to automate):

  UPDATE hostels h
  SET company_id = (
      SELECT e.company_id
      FROM employees e
      WHERE e.hostel_id = h.id AND e.deleted_at IS NULL
      GROUP BY e.company_id
      ORDER BY COUNT(*) DESC
      LIMIT 1
  )
  WHERE h.company_id IS NULL;

This guesses each hostel's company from the company most of its current
occupants belong to. Run it in a transaction, eyeball the diff, commit
only if the assignments look right.
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = "2c8f5e9a1b34"
down_revision: Union[str, Sequence[str], None] = "1a7c4d9b2e80"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        "hostels",
        sa.Column("company_id", sa.Integer(), nullable=True),
    )
    op.create_foreign_key(
        "fk_hostels_company_id",
        "hostels", "companies",
        ["company_id"], ["id"],
    )
    op.create_index(
        "ix_hostels_company_id",
        "hostels",
        ["company_id"],
        unique=False,
    )


def downgrade() -> None:
    op.drop_index("ix_hostels_company_id", table_name="hostels")
    op.drop_constraint("fk_hostels_company_id", "hostels", type_="foreignkey")
    op.drop_column("hostels", "company_id")
