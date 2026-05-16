"""Admin CRUD for CompanyHoliday + a read-side helper used by leave +
payroll integrations in the next two commits.
"""
from datetime import date, datetime, timezone

from fastapi import HTTPException
from sqlalchemy.orm import Session

from app.core.permissions import is_super_admin, same_company
from app.database.database import with_transaction
from app.models.holiday import CompanyHoliday


def _assert_can_touch(actor, company_id: int) -> None:
    if not same_company(actor, company_id):
        raise HTTPException(
            403, "Cannot manage holidays for another company"
        )


def _resolve_company_id(actor, payload_company_id: int) -> int:
    """office_admin's company_id is forced to their own. super_admin
    can target any. Smuggling another company_id past their scope
    is refused at the gate."""
    if is_super_admin(actor):
        return payload_company_id
    if payload_company_id != actor.company_id:
        raise HTTPException(
            403, "Cannot create a holiday in another company"
        )
    return actor.company_id


def create_holiday(db: Session, data, actor) -> CompanyHoliday:
    company_id = _resolve_company_id(actor, data.company_id)

    existing = (
        db.query(CompanyHoliday)
        .filter(
            CompanyHoliday.company_id == company_id,
            CompanyHoliday.date == data.date,
            CompanyHoliday.deleted_at.is_(None),
        )
        .first()
    )
    if existing:
        raise HTTPException(
            400,
            f"A holiday already exists for {data.date.isoformat()} in this "
            f"company. Update the existing entry instead."
        )

    holiday = CompanyHoliday(
        company_id=company_id,
        date=data.date,
        name=data.name,
        created_by=actor.id,
    )
    with with_transaction(db):
        db.add(holiday)
    db.refresh(holiday)
    return holiday


def bulk_create_holidays(
    db: Session, company_id: int, items, actor
) -> tuple[list[CompanyHoliday], list[dict]]:
    """Continue on per-row failures (mostly duplicates) and return
    (created, skipped). Each `skipped` entry is
    {"date": "YYYY-MM-DD", "reason": str}.

    company_id is already scope-resolved by the caller."""
    created: list[CompanyHoliday] = []
    skipped: list[dict] = []

    for item in items:
        try:
            existing = (
                db.query(CompanyHoliday)
                .filter(
                    CompanyHoliday.company_id == company_id,
                    CompanyHoliday.date == item.date,
                    CompanyHoliday.deleted_at.is_(None),
                )
                .first()
            )
            if existing:
                skipped.append({
                    "date": item.date.isoformat(),
                    "reason": "Holiday already exists for this date",
                })
                continue

            holiday = CompanyHoliday(
                company_id=company_id,
                date=item.date,
                name=item.name,
                created_by=actor.id,
            )
            db.add(holiday)
            db.flush()  # make the row visible for the next iteration
            created.append(holiday)
        except Exception as exc:
            db.rollback()
            skipped.append({
                "date": item.date.isoformat(),
                "reason": str(exc),
            })

    db.commit()
    for h in created:
        db.refresh(h)
    return created, skipped


def get_holiday(
    db: Session, holiday_id: int, actor
) -> CompanyHoliday:
    holiday = (
        db.query(CompanyHoliday)
        .filter(
            CompanyHoliday.id == holiday_id,
            CompanyHoliday.deleted_at.is_(None),
        )
        .first()
    )
    if not holiday:
        raise HTTPException(404, "Holiday not found")
    _assert_can_touch(actor, holiday.company_id)
    return holiday


def list_holidays(
    db: Session,
    actor,
    company_id: int | None = None,
    year: int | None = None,
    month: int | None = None,
):
    """Admin list. office_admin sees their own company; super_admin
    must pass company_id (consistent with the reports module)."""
    if is_super_admin(actor):
        if company_id is None:
            raise HTTPException(
                400, "super_admin must pass company_id to list holidays"
            )
    else:
        company_id = actor.company_id

    query = db.query(CompanyHoliday).filter(
        CompanyHoliday.company_id == company_id,
        CompanyHoliday.deleted_at.is_(None),
    )
    if year is not None:
        query = query.filter(
            CompanyHoliday.date >= date(year, 1, 1),
            CompanyHoliday.date <= date(year, 12, 31),
        )
    if month is not None:
        if year is None:
            raise HTTPException(
                400, "month filter requires year"
            )
        from calendar import monthrange
        _, last = monthrange(year, month)
        query = query.filter(
            CompanyHoliday.date >= date(year, month, 1),
            CompanyHoliday.date <= date(year, month, last),
        )

    return query.order_by(CompanyHoliday.date).all()


def update_holiday(
    db: Session, holiday_id: int, data, actor
) -> CompanyHoliday:
    holiday = get_holiday(db, holiday_id, actor)
    update_data = data.model_dump(exclude_unset=True)

    new_date = update_data.get("date")
    if new_date is not None and new_date != holiday.date:
        collision = (
            db.query(CompanyHoliday)
            .filter(
                CompanyHoliday.company_id == holiday.company_id,
                CompanyHoliday.date == new_date,
                CompanyHoliday.id != holiday.id,
                CompanyHoliday.deleted_at.is_(None),
            )
            .first()
        )
        if collision:
            raise HTTPException(
                400,
                f"Another holiday already exists on {new_date.isoformat()}",
            )

    with with_transaction(db):
        for key, value in update_data.items():
            setattr(holiday, key, value)
        holiday.updated_by = actor.id
    db.refresh(holiday)
    return holiday


def delete_holiday(
    db: Session, holiday_id: int, actor
) -> CompanyHoliday:
    holiday = get_holiday(db, holiday_id, actor)
    with with_transaction(db):
        holiday.deleted_at = datetime.now(timezone.utc)
        holiday.updated_by = actor.id
    return holiday


# ---------------------------------------------------------------------------
# Read-side helper used by leave + payroll integrations
# ---------------------------------------------------------------------------

def holiday_dates_in_range(
    db: Session, company_id: int, start: date, end: date
) -> set[date]:
    """Return the set of holiday dates between [start, end] (inclusive)
    for a company. Used by leave-day counting and payroll LWP exclusion.

    Returning a set (not a list) so callers can do O(1) `date in set`
    checks per row they're inspecting.
    """
    rows = (
        db.query(CompanyHoliday.date)
        .filter(
            CompanyHoliday.company_id == company_id,
            CompanyHoliday.deleted_at.is_(None),
            CompanyHoliday.date >= start,
            CompanyHoliday.date <= end,
        )
        .all()
    )
    return {r.date for r in rows}
