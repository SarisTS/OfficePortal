from sqlalchemy.orm import Session
from fastapi import HTTPException
from datetime import datetime, timezone

from app.models.role import Role
from app.core.logger import get_logger
from app.services.audit import log_audit, snapshot

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
        db.flush()
        # Roles are global (no company_id), so company_id stays None
        # on the audit row.
        log_audit(
            db, actor=user, action="role.create",
            entity_type="role", entity_id=db_role.id,
            after=snapshot(db_role),
        )
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

        before = snapshot(role)

        for key, value in update_data.items():
            setattr(role, key, value)

        role.updated_by = user.id

        db.flush()
        log_audit(
            db, actor=user, action="role.update",
            entity_type="role", entity_id=role.id,
            before=before, after=snapshot(role),
        )
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

        before = snapshot(role)
        role.deleted_at = datetime.now(timezone.utc)
        role.updated_by = user.id

        log_audit(
            db, actor=user, action="role.delete",
            entity_type="role", entity_id=role.id, before=before,
        )
        db.commit()

        return role

    except Exception:
        db.rollback()
        logger.exception("Error deleting role")
        raise