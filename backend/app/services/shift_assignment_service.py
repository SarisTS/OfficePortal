from app.models.employee import Employee
from app.models.attendance import Shift
from app.models.assignment import EmployeeShiftAssignment
from fastapi import HTTPException
from sqlalchemy import or_

from app.crud.auth import is_global_admin

class ShiftAssignmentService:

    @staticmethod
    def assign_shift(db, data, user):

        # 🔹 Get employee
        employee = db.query(Employee).filter(
            Employee.id == data.employee_id,
            Employee.deleted_at == None
        ).first()

        if not employee:
            raise HTTPException(404, "Employee not found")

        # 🔐 ACCESS CONTROL
        if not is_global_admin(user):
            if employee.company_id != user.company_id:
                raise HTTPException(403, "Not allowed")

        # 🔹 Get shift (IMPORTANT FIX)
        shift = db.query(Shift).filter(
            Shift.id == data.shift_id,
            Shift.deleted_at == None
        ).first()

        if not shift:
            raise HTTPException(404, "Shift not found")

        # 🔐 Company validation (VERY IMPORTANT)
        if shift.company_id != employee.company_id:
            raise HTTPException(400, "Shift does not belong to employee company")

        # 🔴 Overlap check (improved)
        overlap = db.query(EmployeeShiftAssignment).filter(
            EmployeeShiftAssignment.employee_id == data.employee_id,
            EmployeeShiftAssignment.start_date <= data.start_date,
            or_(
                EmployeeShiftAssignment.end_date == None,
                EmployeeShiftAssignment.end_date >= data.start_date
            )
        ).first()

        if overlap:
            raise HTTPException(400, "Shift overlap detected")

        # ✅ Create assignment
        assignment = EmployeeShiftAssignment(**data.model_dump())
        assignment.created_by = user.id

        db.add(assignment)
        db.commit()
        db.refresh(assignment)

        return assignment
    
    @staticmethod
    def change_shift(db, employee_id, new_shift_id, start_date, user):

        # 🔹 Get employee
        employee = db.query(Employee).filter(
            Employee.id == employee_id,
            Employee.deleted_at == None
        ).first()

        if not employee:
            raise HTTPException(404, "Employee not found")

        # 🔐 Access control
        if not is_global_admin(user):
            if employee.company_id != user.company_id:
                raise HTTPException(403, "Not allowed")

        # 🔹 Lock current shift
        current = db.query(EmployeeShiftAssignment).filter(
            EmployeeShiftAssignment.employee_id == employee_id,
            EmployeeShiftAssignment.end_date == None
        ).with_for_update().first()

        if not current:
            raise HTTPException(404, "No active shift")

        # 🔹 Validate new shift
        new_shift = db.query(Shift).filter(
            Shift.id == new_shift_id,
            Shift.deleted_at == None
        ).first()

        if not new_shift:
            raise HTTPException(404, "Shift not found")

        # 🔐 Company validation
        if new_shift.company_id != employee.company_id:
            raise HTTPException(400, "Shift mismatch")

        # 🔚 Close current shift
        current.end_date = start_date

        # 🆕 New assignment
        new_assignment = EmployeeShiftAssignment(
            employee_id=employee_id,
            shift_id=new_shift_id,
            start_date=start_date,
            created_by=user.id
        )

        db.add(new_assignment)
        db.commit()

        return new_assignment
    