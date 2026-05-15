from fastapi import HTTPException
from sqlalchemy.orm import Session
from app.models.company import Company
from app.models.assignment import CompanyLocation
from app.crud.auth import is_global_admin
from datetime import datetime


class CompanyLocationService:

    @staticmethod
    def create_location(db: Session, data, user):

        # 🔐 Access control
        if not is_global_admin(user):
            if data.company_id != user.company_id:
                raise HTTPException(403, "Not allowed")

        # 🔍 Validate company
        company = db.query(Company).filter(
            Company.id == data.company_id
        ).first()

        if not company:
            raise HTTPException(404, "Company not found")

        # 🔴 Ensure only one primary location
        if data.is_primary:
            db.query(CompanyLocation).filter(
                CompanyLocation.company_id == data.company_id,
                CompanyLocation.is_primary == True
            ).update({"is_primary": False})

        location = CompanyLocation(**data.model_dump())

        db.add(location)
        db.commit()
        db.refresh(location)

        return location
    
    @staticmethod
    def get_locations(db: Session, user, skip: int = 0, limit: int = 10):

        query = db.query(CompanyLocation).filter(
            CompanyLocation.deleted_at == None
        )

        if not is_global_admin(user):
            query = query.filter(
                CompanyLocation.company_id == user.company_id
            )

        total = query.count()
        items = query.order_by(CompanyLocation.id).offset(skip).limit(limit).all()
        return total, items
    

    @staticmethod
    def get_location(db: Session, location_id: int, user):

        location = db.query(CompanyLocation).filter(
            CompanyLocation.id == location_id,
            CompanyLocation.deleted_at == None
        ).first()

        if not location:
            raise HTTPException(404, "Location not found")

        if not is_global_admin(user):
            if location.company_id != user.company_id:
                raise HTTPException(403, "Not allowed")

        return location


    @staticmethod
    def update_location(db: Session, location_id: int, data, user):

        location = CompanyLocationService.get_location(db, location_id, user)

        if data.is_primary:
            db.query(CompanyLocation).filter(
                CompanyLocation.company_id == location.company_id,
                CompanyLocation.id != location_id
            ).update({"is_primary": False})

        for k, v in data.model_dump(exclude_unset=True).items():
            setattr(location, k, v)

        db.commit()
        db.refresh(location)

        return location
    
    @staticmethod
    def delete_location(db: Session, location_id: int, user):

        location = CompanyLocationService.get_location(db, location_id, user)

        location.deleted_at = datetime.utcnow()

        db.commit()

        return True