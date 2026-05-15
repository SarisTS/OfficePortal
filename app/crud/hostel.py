from datetime import datetime, timezone
from fastapi import HTTPException

from app.models.hostel import Hostel
from app.core.logger import get_logger

logger = get_logger()


# NOTE on access control: the Hostel model has no company_id column —
# only a location_id pointing at the geographic Location table. There is
# no Hostel↔Company association in the schema, so "scope hostel mutations
# to the actor's company" cannot be expressed without a schema change.
# Hostels are therefore treated as global infrastructure that any admin
# (router require_admin → super_admin or office_admin) may manage. If
# per-company scoping is needed, add Hostel.company_id (or a join table)
# in a follow-up migration and tighten the checks below.

def create_hostel(db, hostel, user):
    try:
        # 🔒 Duplicate check
        existing = db.query(Hostel).filter(
            Hostel.name == hostel.name,
            Hostel.deleted_at == None
        ).first()

        if existing:
            raise HTTPException(400, "Hostel already exists")

        db_hostel = Hostel(**hostel.model_dump())
        db_hostel.created_by = user.id

        db.add(db_hostel)
        db.commit()
        db.refresh(db_hostel)

        logger.info(f"Hostel created: {db_hostel.id}")

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

    return hostel


def get_hostels(db, user, skip=0, limit=10):
    query = db.query(Hostel).filter(Hostel.deleted_at == None)

    return query.offset(skip).limit(limit).all()


def update_hostel(db, hostel_id, data, user):
    try:
        hostel = db.query(Hostel).filter(
            Hostel.id == hostel_id,
            Hostel.deleted_at == None
        ).first()

        if not hostel:
            return None

        update_data = data.model_dump(exclude_unset=True)

        # 🔒 Duplicate check
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

        hostel.deleted_at = datetime.now(timezone.utc)
        hostel.updated_by = user.id

        db.commit()

        return hostel

    except Exception:
        db.rollback()
        logger.exception("Error deleting hostel")
        raise