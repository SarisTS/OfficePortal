from datetime import datetime, timezone, timedelta

from fastapi import HTTPException

from app.core.permissions import is_super_admin, same_company
from app.models.attendance import Shift


class ShiftService:
    """Shift CRUD.

    Access model:
      super_admin   — global; can create/edit/delete shifts for any company.
      office_admin  — scoped; can manage only shifts where
                      ``shift.company_id == user.company_id``.

    The router already gates these endpoints behind require_admin, so this
    service trusts the caller is one of the two admin roles and only
    enforces company scope.
    """

    @staticmethod
    def create_shift(db, data, user):

        # office_admin can only create shifts for their own company.
        # The ShiftCreate schema requires a company_id from the caller;
        # for office_admin we force it to their own to prevent a payload
        # smuggling a different company_id past the gate.
        if not is_super_admin(user):
            if data.company_id != user.company_id:
                raise HTTPException(
                    403, "Cannot create a shift for another company"
                )

        shift = Shift(**data.model_dump())
        shift.created_by = user.id

        db.add(shift)
        db.commit()
        db.refresh(shift)

        return shift

    @staticmethod
    def get_shifts(db, user, skip: int = 0, limit: int = 10):

        base = db.query(Shift).filter(Shift.deleted_at == None)
        # office_admin sees only their own company's shifts.
        if not is_super_admin(user):
            base = base.filter(Shift.company_id == user.company_id)

        total = base.count()
        items = base.order_by(Shift.id).offset(skip).limit(limit).all()
        return total, items

    @staticmethod
    def get_shift(db, shift_id, user):

        shift = db.query(Shift).filter(
            Shift.id == shift_id,
            Shift.deleted_at == None,
        ).first()

        if not shift:
            raise HTTPException(404, "Shift not found")

        # office_admin can only see shifts within their own company.
        if not same_company(user, shift.company_id):
            raise HTTPException(403, "Not allowed")

        return shift

    @staticmethod
    def get_shifts_by_company(db, company_id, user, skip: int = 0, limit: int = 10):

        # office_admin cannot query shifts in another company.
        if not is_super_admin(user) and company_id != user.company_id:
            raise HTTPException(403, "Not allowed")

        base = db.query(Shift).filter(
            Shift.company_id == company_id,
            Shift.deleted_at == None,
        )
        total = base.count()
        items = base.order_by(Shift.id).offset(skip).limit(limit).all()
        return total, items

    @staticmethod
    def update_shift(db, shift_id, data, user):

        # get_shift already enforces same-company for office_admin and
        # raises 403/404 as appropriate.
        shift = ShiftService.get_shift(db, shift_id, user)

        update_data = data.model_dump(exclude_unset=True)

        # If the payload tries to move the shift to a different company,
        # office_admin cannot do that. super_admin can.
        new_company_id = update_data.get("company_id")
        if new_company_id is not None and not is_super_admin(user):
            if new_company_id != user.company_id:
                raise HTTPException(
                    403, "Cannot move a shift to another company"
                )

        for k, v in update_data.items():
            setattr(shift, k, v)
        shift.updated_by = user.id

        db.commit()
        db.refresh(shift)
        return shift

    @staticmethod
    def delete_shift(db, shift_id, user):

        # get_shift enforces same-company for office_admin.
        shift = ShiftService.get_shift(db, shift_id, user)

        shift.deleted_at = datetime.now(timezone.utc)
        shift.updated_by = user.id
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
