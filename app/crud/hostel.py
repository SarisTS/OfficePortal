from datetime import datetime, timezone
from fastapi import HTTPException

from app.models.hostel import Hostel
from app.crud.auth import is_global_admin
from app.core.logger import get_logger

logger = get_logger()

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

        if not is_global_admin(user):
            raise HTTPException(403, "Not allowed")

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

        if not is_global_admin(user):
            raise HTTPException(403, "Not allowed")

        hostel.deleted_at = datetime.now(timezone.utc)
        hostel.updated_by = user.id

        db.commit()

        return hostel

    except Exception:
        db.rollback()
        logger.exception("Error deleting hostel")
        raise