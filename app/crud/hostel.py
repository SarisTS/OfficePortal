from datetime import datetime, timezone
from fastapi import HTTPException

from app.core.logger import get_logger
from app.core.permissions import is_super_admin
from app.models.hostel import Hostel

logger = get_logger()


# Access model:
#   super_admin   — global; can manage any hostel including NULL-company (legacy) rows.
#   office_admin  — scoped; can manage hostels where company_id == their company_id.
#                   May READ NULL-company (legacy) rows so existing data isn't
#                   invisible to them, but cannot MODIFY a NULL row until
#                   super_admin classifies it.


def create_hostel(db, hostel, user):
    try:
        # 🔒 Duplicate check (kept intentionally broad — the schema-level
        # UniqueConstraint("name", "location_id") is the authoritative
        # rule; this is a friendlier error for the common case).
        existing = db.query(Hostel).filter(
            Hostel.name == hostel.name,
            Hostel.deleted_at == None
        ).first()

        if existing:
            raise HTTPException(400, "Hostel already exists")

        data = hostel.model_dump()

        # 🔒 Tenant scoping for create
        if is_super_admin(user):
            # super_admin must say which company the hostel belongs to,
            # OR explicitly NULL it (rare — only when modelling a truly
            # shared facility). Either is acceptable; nothing to enforce.
            pass
        else:
            # office_admin: ignore any company_id in the payload and
            # always stamp their own. Refuse if they tried to set someone
            # else's company_id (could be a smuggle attempt).
            payload_company = data.get("company_id")
            if payload_company is not None and payload_company != user.company_id:
                raise HTTPException(
                    403, "Cannot create a hostel in another company"
                )
            data["company_id"] = user.company_id

        db_hostel = Hostel(**data)
        db_hostel.created_by = user.id

        db.add(db_hostel)
        db.commit()
        db.refresh(db_hostel)

        logger.info(
            f"Hostel created: {db_hostel.id} (company={db_hostel.company_id})"
        )

        return db_hostel

    except Exception:
        db.rollback()
        logger.exception("Error creating hostel")
        raise


def get_hostel(db, hostel_id, user):
    hostel = db.query(Hostel).filter(
        Hostel.id == hostel_id,
        Hostel.deleted_at == None
    ).first()

    if not hostel:
        return None

    # office_admin can read their own company's hostels and legacy NULL
    # rows. Anything else → 403. (Legacy rows are read-only for them;
    # update/delete re-check.)
    if not is_super_admin(user):
        if hostel.company_id is not None and hostel.company_id != user.company_id:
            raise HTTPException(403, "Not allowed")

    return hostel


def get_hostels(db, user, skip=0, limit=10):
    query = db.query(Hostel).filter(Hostel.deleted_at == None)

    if not is_super_admin(user):
        # Own company OR legacy NULL rows
        query = query.filter(
            (Hostel.company_id == user.company_id) | (Hostel.company_id.is_(None))
        )

    return query.offset(skip).limit(limit).all()


def update_hostel(db, hostel_id, data, user):
    try:
        hostel = db.query(Hostel).filter(
            Hostel.id == hostel_id,
            Hostel.deleted_at == None
        ).first()

        if not hostel:
            return None

        # 🔒 Tenant scoping for update — office_admin can only modify
        # hostels in their own company. NULL-company (legacy) rows are
        # super_admin-only for mutations until super_admin classifies
        # them.
        if not is_super_admin(user):
            if hostel.company_id != user.company_id:
                raise HTTPException(403, "Not allowed")

        update_data = data.model_dump(exclude_unset=True)

        # Block office_admin from moving a hostel into another company
        # (or out of theirs).
        new_company_id = update_data.get("company_id")
        if new_company_id is not None and not is_super_admin(user):
            if new_company_id != user.company_id:
                raise HTTPException(
                    403, "Cannot move a hostel to another company"
                )

        # 🔒 Duplicate name check
        if "name" in update_data:
            existing = db.query(Hostel).filter(
                Hostel.name == update_data["name"],
                Hostel.id != hostel_id,
                Hostel.deleted_at == None
            ).first()

            if existing:
                raise HTTPException(400, "Hostel already exists")

        for key, value in update_data.items():
            setattr(hostel, key, value)

        hostel.updated_by = user.id

        db.commit()
        db.refresh(hostel)

        return hostel

    except Exception:
        db.rollback()
        logger.exception("Error updating hostel")
        raise


def delete_hostel(db, hostel_id, user):
    try:
        hostel = db.query(Hostel).filter(
            Hostel.id == hostel_id,
            Hostel.deleted_at == None
        ).first()

        if not hostel:
            return None

        # Same tenant rule as update.
        if not is_super_admin(user):
            if hostel.company_id != user.company_id:
                raise HTTPException(403, "Not allowed")

        hostel.deleted_at = datetime.now(timezone.utc)
        hostel.updated_by = user.id

        db.commit()

        return hostel

    except Exception:
        db.rollback()
        logger.exception("Error deleting hostel")
        raise
