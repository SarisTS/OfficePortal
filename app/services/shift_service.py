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
    def get_shifts(db, user):

        if not is_global_admin(user):
            raise HTTPException(403, "Not allowed")
        
        return db.query(Shift).filter(
            Shift.deleted_at == None
        ).all()

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
    def get_shifts_by_company(db, company_id, user):

        if not is_global_admin(user):
            raise HTTPException(403, "Not allowed")
        
        shifts = db.query(Shift).filter(
            Shift.company_id == company_id,
            Shift.deleted_at == None
        ).all()

        if not shifts:
            raise HTTPException(404, "Shifts not found for this company")

        return shifts

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