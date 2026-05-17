"""phase 3 schema hardening

Revision ID: 1a7c4d9b2e80
Revises: c2cd75ce0f48
Create Date: 2026-05-15

What this migration does
========================

1. Adds AuditMixin columns (created_at, updated_at, deleted_at, created_by,
   updated_by, is_deleted, is_active) to the four food tables, which were
   the only tables without them. Server defaults so existing rows backfill.

2. Adds missing referential integrity:
     - food_selections.employee_id  -> employees.id  (was a free Integer)
     - food_selections.company_id   -> companies.id  (was a free Integer; nullable)
     - daily_menus.company_id       -> companies.id  (was a free Integer; nullable)

3. Adds natural-key uniqueness:
     - shifts (company_id, name)
     - company_locations (company_id, name)
     - daily_menus (company_id, date)
     - daily_menu_items (daily_menu_id, food_item_id)

4. New indexes for common access patterns:
     - leaves.status                       (admin filtering pending)
     - attendance (company_id, date)       (company-wide reporting)
     - locations.country_id/state_id/city_id  (geo lookup)
     - shifts.company_id                   (FK lookup)
     - daily_menus (company_id, date)      (menu lookup)

5. Swaps the plain UNIQUE indexes on employees(email/mobile/roll_no/google_id)
   for PARTIAL unique indexes WHERE deleted_at IS NULL AND <col> IS NOT NULL.
   This lets a previously-soft-deleted employee's email/mobile/roll_no be
   re-used by a new hire without violating uniqueness, while still preventing
   two ACTIVE rows from claiming the same identifier.

6. Drops three duplicate non-unique indexes on employees (idx_employee_email,
   idx_employee_mobile, idx_employee_roll) that covered the same columns as
   the column-level `index=True` (which already created ix_employees_*).

------------------------------------------------------------------------------
PRE-FLIGHT CHECKS  ---- RUN ON A DEV COPY OF YOUR DATA BEFORE APPLYING ----
------------------------------------------------------------------------------

The new uniqueness constraints and FKs will REFUSE TO CREATE if the data
violates them. Run each query first; expected result is "0 rows". If any
returns rows, you must clean those up before this migration can succeed.

-- (A) Duplicate shift names within a company
SELECT company_id, name, COUNT(*)
FROM shifts
WHERE deleted_at IS NULL
GROUP BY company_id, name
HAVING COUNT(*) > 1;

-- (B) Duplicate company_location names within a company
SELECT company_id, name, COUNT(*)
FROM company_locations
WHERE deleted_at IS NULL
GROUP BY company_id, name
HAVING COUNT(*) > 1;

-- (C) Duplicate daily_menus for the same (company_id, date)
SELECT company_id, date, COUNT(*)
FROM daily_menus
GROUP BY company_id, date
HAVING COUNT(*) > 1;

-- (D) Same food appearing twice on one daily_menu
SELECT daily_menu_id, food_item_id, COUNT(*)
FROM daily_menu_items
GROUP BY daily_menu_id, food_item_id
HAVING COUNT(*) > 1;

-- (E) food_selections with employee_id that no longer exists
SELECT fs.id, fs.employee_id
FROM food_selections fs
LEFT JOIN employees e ON e.id = fs.employee_id
WHERE e.id IS NULL;

-- (F) food_selections with non-null company_id that doesn't exist
SELECT fs.id, fs.company_id
FROM food_selections fs
LEFT JOIN companies c ON c.id = fs.company_id
WHERE fs.company_id IS NOT NULL AND c.id IS NULL;

-- (G) daily_menus with non-null company_id that doesn't exist
SELECT dm.id, dm.company_id
FROM daily_menus dm
LEFT JOIN companies c ON c.id = dm.company_id
WHERE dm.company_id IS NOT NULL AND c.id IS NULL;

The employee partial-unique swap (#5) is data-safe: the OLD constraint
already prevents duplicate emails/mobiles/roll_nos across all rows, so no
active duplicates can exist today. After the swap, soft-deleted rows are
allowed to share identifiers with each other and with active rows.

------------------------------------------------------------------------------
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = "1a7c4d9b2e80"
down_revision: Union[str, Sequence[str], None] = "c2cd75ce0f48"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


# Tables that need AuditMixin added.
_FOOD_TABLES = ("food_items", "daily_menus", "daily_menu_items", "food_selections")


def upgrade() -> None:
    # ------------------------------------------------------------------
    # 1. AuditMixin columns on food tables
    # ------------------------------------------------------------------
    for tbl in _FOOD_TABLES:
        op.add_column(
            tbl,
            sa.Column(
                "created_at",
                sa.DateTime(timezone=True),
                server_default=sa.text("NOW()"),
                nullable=False,
            ),
        )
        op.add_column(
            tbl,
            sa.Column(
                "updated_at",
                sa.DateTime(timezone=True),
                server_default=sa.text("NOW()"),
                nullable=False,
            ),
        )
        op.add_column(
            tbl,
            sa.Column("deleted_at", sa.DateTime(timezone=True), nullable=True),
        )
        op.add_column(tbl, sa.Column("created_by", sa.Integer(), nullable=True))
        op.add_column(tbl, sa.Column("updated_by", sa.Integer(), nullable=True))
        op.add_column(
            tbl,
            sa.Column(
                "is_deleted",
                sa.Boolean(),
                server_default=sa.text("false"),
                nullable=False,
            ),
        )
        op.add_column(
            tbl,
            sa.Column(
                "is_active",
                sa.Boolean(),
                server_default=sa.text("true"),
                nullable=False,
            ),
        )

    # ------------------------------------------------------------------
    # 2. Missing FKs on food tables
    #    (Pre-flight checks E/F/G must be clean before these succeed.)
    # ------------------------------------------------------------------
    op.create_foreign_key(
        "fk_food_selections_employee_id",
        "food_selections", "employees",
        ["employee_id"], ["id"],
    )
    op.create_foreign_key(
        "fk_food_selections_company_id",
        "food_selections", "companies",
        ["company_id"], ["id"],
    )
    op.create_foreign_key(
        "fk_daily_menus_company_id",
        "daily_menus", "companies",
        ["company_id"], ["id"],
    )

    # ------------------------------------------------------------------
    # 3. Natural-key uniqueness
    #    (Pre-flight checks A/B/C/D must be clean before these succeed.)
    # ------------------------------------------------------------------
    op.create_unique_constraint(
        "uq_shift_company_name", "shifts", ["company_id", "name"]
    )
    op.create_unique_constraint(
        "uq_company_location_name", "company_locations", ["company_id", "name"]
    )
    op.create_unique_constraint(
        "uq_daily_menu_company_date", "daily_menus", ["company_id", "date"]
    )
    op.create_unique_constraint(
        "uq_menu_item", "daily_menu_items", ["daily_menu_id", "food_item_id"]
    )

    # ------------------------------------------------------------------
    # 4. New indexes
    # ------------------------------------------------------------------
    op.create_index("idx_shift_company", "shifts", ["company_id"])
    op.create_index("idx_leave_status", "leaves", ["status"])
    op.create_index(
        "idx_attendance_company_date", "attendance", ["company_id", "date"]
    )
    op.create_index("idx_locations_country", "locations", ["country_id"])
    op.create_index("idx_locations_state", "locations", ["state_id"])
    op.create_index("idx_locations_city", "locations", ["city_id"])
    op.create_index(
        "idx_daily_menu_company_date", "daily_menus", ["company_id", "date"]
    )

    # ------------------------------------------------------------------
    # 5. Drop redundant non-unique employee indexes
    #    (idx_employee_email/mobile/roll covered the same columns as
    #     ix_employees_email/mobile/roll_no, which already exist via the
    #     column-level index=True.)
    # ------------------------------------------------------------------
    op.drop_index("idx_employee_email", table_name="employees")
    op.drop_index("idx_employee_mobile", table_name="employees")
    op.drop_index("idx_employee_roll", table_name="employees")

    # ------------------------------------------------------------------
    # 6. Swap plain UNIQUE → partial UNIQUE WHERE deleted_at IS NULL
    #    All four old indexes are simultaneously unique + lookup; we
    #    replace each with a non-unique lookup index plus a partial unique.
    # ------------------------------------------------------------------
    for col in ("email", "mobile", "roll_no", "google_id"):
        old_index = f"ix_employees_{col}"

        # Drop the old plain-unique index
        op.drop_index(old_index, table_name="employees")

        # Recreate as a non-unique lookup index (matches the model's
        # column-level index=True after the swap).
        op.create_index(old_index, "employees", [col], unique=False)

        # Add the partial unique that enforces "no two active rows with
        # the same value" while permitting soft-deleted collisions.
        op.create_index(
            f"uq_employees_{col}_active",
            "employees",
            [col],
            unique=True,
            postgresql_where=sa.text(
                f"deleted_at IS NULL AND {col} IS NOT NULL"
            ),
        )


def downgrade() -> None:
    # Reverse order of upgrade().

    # 6. Revert employee partial-unique swap
    for col in ("email", "mobile", "roll_no", "google_id"):
        partial_name = f"uq_employees_{col}_active"
        lookup_name = f"ix_employees_{col}"

        op.drop_index(partial_name, table_name="employees")
        op.drop_index(lookup_name, table_name="employees")
        # Recreate the original plain-unique index
        op.create_index(lookup_name, "employees", [col], unique=True)

    # 5. Recreate the redundant non-unique employee indexes
    op.create_index("idx_employee_roll", "employees", ["roll_no"])
    op.create_index("idx_employee_mobile", "employees", ["mobile"])
    op.create_index("idx_employee_email", "employees", ["email"])

    # 4. Drop new indexes
    op.drop_index("idx_daily_menu_company_date", table_name="daily_menus")
    op.drop_index("idx_locations_city", table_name="locations")
    op.drop_index("idx_locations_state", table_name="locations")
    op.drop_index("idx_locations_country", table_name="locations")
    op.drop_index("idx_attendance_company_date", table_name="attendance")
    op.drop_index("idx_leave_status", table_name="leaves")
    op.drop_index("idx_shift_company", table_name="shifts")

    # 3. Drop new unique constraints
    op.drop_constraint("uq_menu_item", "daily_menu_items", type_="unique")
    op.drop_constraint("uq_daily_menu_company_date", "daily_menus", type_="unique")
    op.drop_constraint("uq_company_location_name", "company_locations", type_="unique")
    op.drop_constraint("uq_shift_company_name", "shifts", type_="unique")

    # 2. Drop new FKs
    op.drop_constraint(
        "fk_daily_menus_company_id", "daily_menus", type_="foreignkey"
    )
    op.drop_constraint(
        "fk_food_selections_company_id", "food_selections", type_="foreignkey"
    )
    op.drop_constraint(
        "fk_food_selections_employee_id", "food_selections", type_="foreignkey"
    )

    # 1. Drop AuditMixin columns from food tables
    for tbl in _FOOD_TABLES:
        for col in (
            "is_active",
            "is_deleted",
            "updated_by",
            "created_by",
            "deleted_at",
            "updated_at",
            "created_at",
        ):
            op.drop_column(tbl, col)
