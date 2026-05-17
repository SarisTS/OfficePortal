from sqlalchemy.orm import Session
from fastapi import HTTPException
from app.models.company import Company
from app.models.employee import UserTypes
from app.core.logger import get_logger
from app.services.audit import log_audit, snapshot

logger = get_logger()

def create_company(db: Session, company_data, actor):
    try:
        # 🔍 Duplicate check
        existing = db.query(Company).filter(
            Company.name == company_data.name,
            Company.is_active == True
        ).first()

        if existing:
            raise HTTPException(status_code=400, detail="Company already exists")

        # 🔍 Parent validation
        if company_data.parent_company_id:
            parent = db.query(Company).filter(
                Company.id == company_data.parent_company_id,
                Company.is_active == True
            ).first()

            if not parent:
                raise HTTPException(status_code=400, detail="Invalid parent company")

        company = Company(**company_data.model_dump())
        company.created_by = actor.id

        db.add(company)
        db.flush()  # populate id for the audit snapshot
        log_audit(
            db, actor=actor, action="company.create",
            entity_type="company", entity_id=company.id,
            company_id=company.id, after=snapshot(company),
        )
        db.commit()
        db.refresh(company)

        logger.info(f"Company created: {company.id}")

        return company

    except Exception as e:
        db.rollback()
        logger.exception("Error creating company")
        raise


def get_companies(db: Session, actor, skip=0, limit=10, name=None):
    """List companies the actor is allowed to see.

    Tenant rule:
      super_admin    → every company in the system
      office_admin   → only the actor's own company

    Previously this returned every row to every caller, so an office_admin
    could enumerate the names and IDs of competing tenants.
    """
    query = db.query(Company).filter(Company.is_active == True)

    if actor.user_type != UserTypes.super_admin:
        if actor.company_id is None:
            # office_admin without a company should never happen, but
            # return empty rather than leak everything.
            return []
        query = query.filter(Company.id == actor.company_id)

    if name:
        query = query.filter(Company.name.ilike(f"%{name}%"))

    return query.offset(skip).limit(limit).all()


def get_company(db: Session, company_id: int, actor):
    """Fetch one company with the same tenant rule as get_companies."""
    if (
        actor.user_type != UserTypes.super_admin
        and company_id != actor.company_id
    ):
        # Treat cross-tenant access as not-found rather than 403 — the
        # router converts None → 404 already, which hides existence.
        return None
    return db.query(Company).filter(
        Company.id == company_id,
        Company.is_active == True
    ).first()


def update_company(db: Session, company_id: int, data, actor):
    try:
        company = db.query(Company).filter(
            Company.id == company_id,
            Company.is_active == True
        ).first()

        if not company:
            return None

        # 🔍 Duplicate name check
        if data.name:
            existing = db.query(Company).filter(
                Company.name == data.name,
                Company.id != company_id,
                Company.is_active == True
            ).first()

            if existing:
                raise HTTPException(status_code=400, detail="Company name already exists")

        # 🔍 Parent validation
        if data.parent_company_id:
            if data.parent_company_id == company_id:
                raise HTTPException(status_code=400, detail="Cannot set itself as parent")

        before = snapshot(company)

        for key, value in data.model_dump(exclude_unset=True).items():
            setattr(company, key, value)

        company.updated_by = actor.id

        db.flush()
        log_audit(
            db, actor=actor, action="company.update",
            entity_type="company", entity_id=company.id,
            company_id=company.id,
            before=before, after=snapshot(company),
        )
        db.commit()
        db.refresh(company)

        logger.info(f"Company updated: {company_id}")

        return company

    except Exception:
        db.rollback()
        logger.exception("Error updating company")
        raise


def delete_company(db: Session, company_id: int, actor):
    try:
        company = db.query(Company).filter(
            Company.id == company_id,
            Company.is_active == True
        ).first()

        if not company:
            return None

        before = snapshot(company)

        company.is_active = False
        company.updated_by = actor.id

        log_audit(
            db, actor=actor, action="company.delete",
            entity_type="company", entity_id=company.id,
            company_id=company.id, before=before,
        )
        db.commit()

        logger.info(f"Company soft deleted: {company_id}")

        return company

    except Exception:
        db.rollback()
        logger.exception("Error deleting company")
        raise