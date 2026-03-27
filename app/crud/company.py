from sqlalchemy.orm import Session
from fastapi import HTTPException
from app.models.company import Company
from app.core.logger import get_logger

logger = get_logger()

def create_company(db: Session, company_data, user_id: int):
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

        company = Company(**company_data.dict())
        company.created_by = user_id

        db.add(company)
        db.commit()
        db.refresh(company)

        logger.info(f"Company created: {company.id}")

        return company

    except Exception as e:
        db.rollback()
        logger.exception("Error creating company")
        raise


def get_companies(db: Session, skip=0, limit=10, name=None):
    query = db.query(Company).filter(Company.is_active == True)

    if name:
        query = query.filter(Company.name.ilike(f"%{name}%"))

    return query.offset(skip).limit(limit).all()


def get_company(db: Session, company_id: int):
    return db.query(Company).filter(
        Company.id == company_id,
        Company.is_active == True
    ).first()


def update_company(db: Session, company_id: int, data, user_id: int):
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

        for key, value in data.dict(exclude_unset=True).items():
            setattr(company, key, value)

        company.updated_by = user_id

        db.commit()
        db.refresh(company)

        logger.info(f"Company updated: {company_id}")

        return company

    except Exception:
        db.rollback()
        logger.exception("Error updating company")
        raise


def delete_company(db: Session, company_id: int, user_id: int):
    try:
        company = db.query(Company).filter(
            Company.id == company_id,
            Company.is_active == True
        ).first()

        if not company:
            return None

        company.is_active = False
        company.updated_by = user_id

        db.commit()

        logger.info(f"Company soft deleted: {company_id}")

        return company

    except Exception:
        db.rollback()
        logger.exception("Error deleting company")
        raise