from sqlalchemy.orm import Session
from fastapi import HTTPException
from datetime import datetime, timezone

from app.models.role import Role
from app.core.logger import get_logger

logger = get_logger()

SYSTEM_ROLES = ["super_admin", "office_admin"]

def create_role(db, role, user):
    try:
        existing = db.query(Role).filter(
            Role.role_name == role.role_name,
            Role.deleted_at == None
        ).first()

        if existing:
            raise HTTPException(400, "Role already exists")

        db_role = Role(**role.model_dump())
        db_role.created_by = user.id

        db.add(db_role)
        db.commit()
        db.refresh(db_role)

        return db_role

    except Exception:
        db.rollback()
        logger.exception("Error creating role")
        raise


def get_roles(db, skip=0, limit=10):
    return db.query(Role).filter(
        Role.deleted_at == None
    ).offset(skip).limit(limit).all()



def get_role(db: Session, role_id: int):

    return db.query(Role).filter(
        Role.id == role_id,
        Role.deleted_at == None
    ).first()



def update_role(db, role_id, data, user):
    try:
        role = db.query(Role).filter(
            Role.id == role_id,
            Role.deleted_at == None
        ).first()

        if not role:
            return None

        if role.role_name in SYSTEM_ROLES:
            raise HTTPException(400, "Cannot modify system roles")

        update_data = data.model_dump(exclude_unset=True)

        if "role_name" in update_data:
            existing = db.query(Role).filter(
                Role.role_name == update_data["role_name"],
                Role.id != role_id,
                Role.deleted_at == None
            ).first()

            if existing:
                raise HTTPException(400, "Role already exists")

        for key, value in update_data.items():
            setattr(role, key, value)

        role.updated_by = user.id

        db.commit()
        db.refresh(role)

        return role

    except Exception:
        db.rollback()
        logger.exception("Error updating role")
        raise



def delete_role(db, role_id, user):
    try:
        role = db.query(Role).filter(
            Role.id == role_id,
            Role.deleted_at == None
        ).first()

        if not role:
            return None

        if role.role_name in SYSTEM_ROLES:
            raise HTTPException(400, "Cannot delete system roles")

        role.deleted_at = datetime.now(timezone.utc)
        role.updated_by = user.id

        db.commit()

        return role

    except Exception:
        db.rollback()
        logger.exception("Error deleting role")
        raise