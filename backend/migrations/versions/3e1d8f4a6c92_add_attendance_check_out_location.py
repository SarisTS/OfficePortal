"""add attendance.check_out_location_id

Revision ID: 3e1d8f4a6c92
Revises: 2c8f5e9a1b34
Create Date: 2026-05-15

Closes a latent bug in services/attendance_service.py: the check-out
handler wrote ``attendance.checkout_location_id = valid_location.id``,
which SQLAlchemy silently set as a Python attribute because no such
column existed. The intent was to track WHERE an employee checks out
(separate from the check-in location, since check-in and check-out can
happen at different sites — office vs. client visit).

Adds the column as a nullable FK to company_locations, indexed for
reverse lookups. Existing rows get NULL (we have no way to retroactively
infer where past check-outs happened).

After this migration is applied, the service code (separate commit) is
fixed to write to the correct column name.
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = "3e1d8f4a6c92"
down_revision: Union[str, Sequence[str], None] = "2c8f5e9a1b34"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        "attendance",
        sa.Column("check_out_location_id", sa.Integer(), nullable=True),
    )
    op.create_foreign_key(
        "fk_attendance_check_out_location_id",
        "attendance", "company_locations",
        ["check_out_location_id"], ["id"],
    )
    op.create_index(
        "ix_attendance_check_out_location_id",
        "attendance",
        ["check_out_location_id"],
        unique=False,
    )


def downgrade() -> None:
    op.drop_index(
        "ix_attendance_check_out_location_id", table_name="attendance"
    )
    op.drop_constraint(
        "fk_attendance_check_out_location_id", "attendance", type_="foreignkey"
    )
    op.drop_column("attendance", "check_out_location_id")
