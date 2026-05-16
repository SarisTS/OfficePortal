"""Admin CRUD for CompanyHoliday + CompanyWeeklyOff, plus a read-side
helper (non_working_dates_in_range) used by leave + payroll services.
"""
from datetime import date, datetime, timedelta, timezone

from fastapi import HTTPException
from sqlalchemy.orm import Session

from app.core.permissions import is_super_admin, same_company
from app.database.database import with_transaction
from app.models.holiday import CompanyHoliday, CompanyWeeklyOff


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
    """Explicit (date-based) holidays only — does NOT include weekly
    off patterns. For the union of both, use non_working_dates_in_range.

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


def _company_weekly_off_days(db: Session, company_id: int) -> set[int]:
    """Set of weekday numbers (0=Mon..6=Sun) that are non-working for
    the company. Empty set when the company has no weekly-off rows."""
    rows = (
        db.query(CompanyWeeklyOff.day_of_week)
        .filter(
            CompanyWeeklyOff.company_id == company_id,
            CompanyWeeklyOff.deleted_at.is_(None),
        )
        .all()
    )
    return {r.day_of_week for r in rows}


def non_working_dates_in_range(
    db: Session, company_id: int, start: date, end: date
) -> set[date]:
    """Union of explicit holidays + expanded weekly-off days for the
    company in [start, end] (inclusive).

    The weekly-off pattern is expanded by walking the date range one
    day at a time and adding any whose weekday() is in the company's
    weekly-off set. O(range_length) — bounded by month/quarter
    boundaries in practice (called for leave + per-month payroll).

    This is what leave-day counting and payroll LWP exclusion should
    consult — see app/services/leave_balance.py:billable_leave_days
    and app/services/payroll.py:_count_absent_days.
    """
    explicit = holiday_dates_in_range(db, company_id, start, end)
    weekly = _company_weekly_off_days(db, company_id)
    if not weekly:
        return explicit

    expanded: set[date] = set()
    cur = start
    while cur <= end:
        if cur.weekday() in weekly:
            expanded.add(cur)
        cur += timedelta(days=1)

    return explicit | expanded


# ---------------------------------------------------------------------------
# Weekly-off CRUD
# ---------------------------------------------------------------------------

def _resolve_weekly_off_company(actor, payload_company_id: int) -> int:
    """Same scope rule as create_holiday: office_admin force-stamped
    to their own company; super_admin can target any."""
    if is_super_admin(actor):
        return payload_company_id
    if payload_company_id != actor.company_id:
        raise HTTPException(
            403, "Cannot create a weekly-off in another company"
        )
    return actor.company_id


def create_weekly_off(db: Session, data, actor) -> CompanyWeeklyOff:
    company_id = _resolve_weekly_off_company(actor, data.company_id)

    existing = (
        db.query(CompanyWeeklyOff)
        .filter(
            CompanyWeeklyOff.company_id == company_id,
            CompanyWeeklyOff.day_of_week == data.day_of_week,
            CompanyWeeklyOff.deleted_at.is_(None),
        )
        .first()
    )
    if existing:
        raise HTTPException(
            400,
            f"Weekly off for day_of_week={data.day_of_week} already exists "
            f"in this company."
        )

    row = CompanyWeeklyOff(
        company_id=company_id,
        day_of_week=data.day_of_week,
        created_by=actor.id,
    )
    with with_transaction(db):
        db.add(row)
    db.refresh(row)
    return row


def list_weekly_offs(db: Session, actor, company_id: int | None = None):
    """Admin list. office_admin sees their own; super_admin must pass
    company_id (consistent with the holiday list rule)."""
    if is_super_admin(actor):
        if company_id is None:
            raise HTTPException(
                400, "super_admin must pass company_id to list weekly offs"
            )
    else:
        company_id = actor.company_id

    return (
        db.query(CompanyWeeklyOff)
        .filter(
            CompanyWeeklyOff.company_id == company_id,
            CompanyWeeklyOff.deleted_at.is_(None),
        )
        .order_by(CompanyWeeklyOff.day_of_week)
        .all()
    )


def delete_weekly_off(db: Session, weekly_off_id: int, actor) -> CompanyWeeklyOff:
    row = (
        db.query(CompanyWeeklyOff)
        .filter(
            CompanyWeeklyOff.id == weekly_off_id,
            CompanyWeeklyOff.deleted_at.is_(None),
        )
        .first()
    )
    if not row:
        raise HTTPException(404, "Weekly off not found")
    if not same_company(actor, row.company_id):
        raise HTTPException(403, "Not allowed")

    with with_transaction(db):
        row.deleted_at = datetime.now(timezone.utc)
        row.updated_by = actor.id
    return row
