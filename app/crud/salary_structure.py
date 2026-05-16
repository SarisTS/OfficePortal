"""Admin CRUD for SalaryStructure.

office_admin can manage structures for employees in their own company;
super_admin is unscoped. Append-only history convention — to change a
salary, POST a new row with a later effective_from rather than mutating
an old one (though Update is allowed for correcting typos on a freshly
created structure).
"""
import csv as _csv
import io as _io
from datetime import date, datetime, timezone

from fastapi import HTTPException
from pydantic import ValidationError
from sqlalchemy.orm import Session

from app.core.permissions import (
    assert_can_access_employee, is_super_admin, same_company,
)
from app.database.database import with_transaction
from app.models.employee import Employee
from app.models.payslip import SalaryStructure
from app.schemas.payslip import SalaryStructureCreate


def _target_employee_or_403(db: Session, employee_id: int, actor):
    """Resolve the target Employee while enforcing the tenant rule:

      super_admin    any employee
      office_admin   same company only
    """
    return assert_can_access_employee(db, employee_id, actor)


def create_structure(db: Session, data, actor) -> SalaryStructure:
    target = _target_employee_or_403(db, data.employee_id, actor)

    # The UNIQUE(employee_id, effective_from) constraint would catch
    # this at flush time, but we surface a friendlier 400 here.
    existing = (
        db.query(SalaryStructure)
        .filter(
            SalaryStructure.employee_id == target.id,
            SalaryStructure.effective_from == data.effective_from,
            SalaryStructure.deleted_at.is_(None),
        )
        .first()
    )
    if existing:
        raise HTTPException(
            400,
            "A salary structure already exists for this employee with "
            "that effective_from date. Edit it, or pick a different date."
        )

    structure = SalaryStructure(
        employee_id=target.id,
        effective_from=data.effective_from,
        basic=data.basic,
        hra=data.hra,
        special_allowance=data.special_allowance,
        other_allowances=data.other_allowances,
        pf=data.pf,
        professional_tax=data.professional_tax,
        tds=data.tds,
        other_deductions=data.other_deductions,
        created_by=actor.id,
    )

    with with_transaction(db):
        db.add(structure)
    db.refresh(structure)
    return structure


def get_structure(db: Session, structure_id: int, actor) -> SalaryStructure:
    structure = (
        db.query(SalaryStructure)
        .filter(
            SalaryStructure.id == structure_id,
            SalaryStructure.deleted_at.is_(None),
        )
        .first()
    )
    if not structure:
        raise HTTPException(404, "Salary structure not found")

    # Tenant check via the target employee
    _target_employee_or_403(db, structure.employee_id, actor)
    return structure


def list_structures_for_employee(
    db: Session, employee_id: int, actor, skip: int = 0, limit: int = 50
):
    target = _target_employee_or_403(db, employee_id, actor)

    base = db.query(SalaryStructure).filter(
        SalaryStructure.employee_id == target.id,
        SalaryStructure.deleted_at.is_(None),
    )
    total = base.count()
    items = (
        base.order_by(SalaryStructure.effective_from.desc())
        .offset(skip)
        .limit(limit)
        .all()
    )
    return total, items


def update_structure(
    db: Session, structure_id: int, data, actor
) -> SalaryStructure:
    """Apply a partial update to amounts on an existing row.

    effective_from cannot be changed (the schema doesn't expose it). To
    move the start date, create a new structure with the new date and
    delete the old one.
    """
    structure = get_structure(db, structure_id, actor)
    update_data = data.model_dump(exclude_unset=True)

    if not update_data:
        return structure

    with with_transaction(db):
        for key, value in update_data.items():
            setattr(structure, key, value)
        structure.updated_by = actor.id
    db.refresh(structure)
    return structure


def delete_structure(
    db: Session, structure_id: int, actor
) -> SalaryStructure:
    structure = get_structure(db, structure_id, actor)
    with with_transaction(db):
        structure.deleted_at = datetime.now(timezone.utc)
        structure.updated_by = actor.id
    return structure


# ---------------------------------------------------------------------------
# Read helper used by /me/salary
# ---------------------------------------------------------------------------

def get_current_structure(
    db: Session, employee_id: int, as_of: date | None = None
) -> SalaryStructure | None:
    """Return the SalaryStructure active for `employee_id` on `as_of`,
    or None if no structure applies on that date.

    "Active" = greatest effective_from that's not in the future, ignoring
    soft-deleted rows. This is the function the payslip generator will
    call from commit 2.
    """
    if as_of is None:
        as_of = date.today()

    return (
        db.query(SalaryStructure)
        .filter(
            SalaryStructure.employee_id == employee_id,
            SalaryStructure.deleted_at.is_(None),
            SalaryStructure.effective_from <= as_of,
        )
        .order_by(SalaryStructure.effective_from.desc())
        .first()
    )


# ---------------------------------------------------------------------------
# Bulk CSV import
# ---------------------------------------------------------------------------

def bulk_import_structures(db: Session, csv_text: str, actor):
    """Parse CSV text + call create_structure per row.

    Same conventions as crud.employee.bulk_import_employees:
      - header maps to SalaryStructureCreate field names
      - unknown columns ignored, empty cells → None
      - per-row failures captured (validation, 403 cross-company,
        duplicate (employee_id, effective_from))
      - row numbering starts at 2 (row 1 = header)

    Tenant scoping is enforced inside create_structure via the
    `_target_employee_or_403` check — office_admin importing for an
    employee in another company gets a 403 captured per-row.

    Returns (created, skipped).
    """
    reader = _csv.DictReader(_io.StringIO(csv_text))
    known_fields = set(SalaryStructureCreate.model_fields.keys())

    created: list[SalaryStructure] = []
    skipped: list[dict] = []

    for row_idx, row in enumerate(reader, start=2):
        cleaned = {
            k: (v if v != "" else None)
            for k, v in row.items()
            if k in known_fields
        }

        try:
            schema = SalaryStructureCreate(**cleaned)
        except ValidationError as exc:
            skipped.append({
                "row_number": row_idx,
                # include_context=False drops the `ctx` field which can
                # carry raw exception objects (ValueError from field
                # validators) that Pydantic's JSON serializer can't
                # encode through the response model.
                "errors": exc.errors(include_context=False),
            })
            continue

        try:
            structure = create_structure(db, schema, actor)
            created.append(structure)
        except HTTPException as exc:
            skipped.append({
                "row_number": row_idx,
                "errors": [{"detail": str(exc.detail)}],
            })
        except Exception as exc:  # defensive
            skipped.append({
                "row_number": row_idx,
                "errors": [{"detail": str(exc)}],
            })

    return created, skipped
