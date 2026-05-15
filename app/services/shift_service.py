from app.models.attendance import Shift
from fastapi import HTTPException
from datetime import datetime, timezone, timedelta
from app.crud.auth import is_global_admin

class ShiftService:

    @staticmethod
    def create_shift(db, data, user):

        # 🔒 Only global admin can create for any company
        if not is_global_admin(user):
            raise HTTPException(403, "Not allowed")

        shift = Shift(**data.model_dump())

        db.add(shift)
        db.commit()
        db.refresh(shift)

        return shift

    @staticmethod
    def get_shifts(db, user, skip: int = 0, limit: int = 10):

        if not is_global_admin(user):
            raise HTTPException(403, "Not allowed")

        base = db.query(Shift).filter(Shift.deleted_at == None)
        total = base.count()
        items = base.order_by(Shift.id).offset(skip).limit(limit).all()
        return total, items

    @staticmethod
    def get_shift(db, shift_id, user):

        if not is_global_admin(user):
            raise HTTPException(403, "Not allowed")

        shift = db.query(Shift).filter(
            Shift.id == shift_id,
            Shift.deleted_at == None
        ).first()

        if not shift:
            raise HTTPException(404, "Shift not found")

        return shift

    @staticmethod
    def get_shifts_by_company(db, company_id, user, skip: int = 0, limit: int = 10):

        if not is_global_admin(user):
            raise HTTPException(403, "Not allowed")

        base = db.query(Shift).filter(
            Shift.company_id == company_id,
            Shift.deleted_at == None,
        )
        total = base.count()
        items = base.order_by(Shift.id).offset(skip).limit(limit).all()
        # Empty page is a valid result — return {total: 0, items: []} rather
        # than 404'ing, which would prevent the caller from distinguishing
        # "no shifts" from "company not found".
        return total, items

    @staticmethod
    def update_shift(db, shift_id, data, user):

        if not is_global_admin(user):
            raise HTTPException(403, "Not allowed")
        
        shift = ShiftService.get_shift(db, shift_id, user)

        for k, v in data.model_dump(exclude_unset=True).items():
            setattr(shift, k, v)

        db.commit()
        db.refresh(shift)
        return shift

    @staticmethod
    def delete_shift(db, shift_id, user):

        if not is_global_admin(user):
            raise HTTPException(403, "Not allowed")
        
        shift = ShiftService.get_shift(db, shift_id, user)

        shift.deleted_at = datetime.now(timezone.utc)
        db.commit()

        return True
    
def resolve_shift_window(shift, now):
    shift_start = datetime.combine(now.date(), shift.start_time)
    shift_end = datetime.combine(now.date(), shift.end_time)

    # 🔥 Night shift handling
    if shift.end_time < shift.start_time:
        shift_end += timedelta(days=1)

        if now < shift_start:
            shift_start -= timedelta(days=1)
            shift_end -= timedelta(days=1)

    return shift_start, shift_end