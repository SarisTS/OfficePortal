from sqlalchemy.orm import Session
from fastapi import HTTPException
from app.models.attendance import Shift
from app.models.employee import Employee
from app.models.assignment import EmployeeShiftAssignment
from datetime import date
from app.crud.auth import is_global_admin


def create_shift(db: Session, data, user):

    shift = Shift(**data.model_dump())
    shift.company_id = user.company_id

    db.add(shift)
    db.commit()
    db.refresh(shift)

    return shift


def get_shifts(db: Session, user):

    return db.query(Shift).filter(
        Shift.company_id == user.company_id
    ).all()


def update_shift(db: Session, shift_id: int, data, user):

    shift = db.query(Shift).filter(
        Shift.id == shift_id,
        Shift.company_id == user.company_id
    ).first()

    if not shift:
        raise HTTPException(404, "Shift not found")

    for key, value in data.model_dump(exclude_unset=True).items():
        setattr(shift, key, value)

    db.commit()
    db.refresh(shift)

    return shift


def delete_shift(db: Session, shift_id: int, user):

    shift = db.query(Shift).filter(
        Shift.id == shift_id,
        Shift.company_id == user.company_id
    ).first()

    if not shift:
        raise HTTPException(404, "Shift not found")

    db.delete(shift)
    db.commit()

    return {"message": "Deleted"}


def assign_shift(db: Session, data, user):

    # 🔒 Get employee
    employee = db.query(Employee).filter(
        Employee.id == data.employee_id,
        Employee.deleted_at == None
    ).first()

    if not employee:
        raise HTTPException(404, "Employee not found")

    # 🔒 Tenant check
    if employee.company_id != user.company_id:
        raise HTTPException(403, "Not allowed")

    # ❌ Overlap check
    overlapping = db.query(EmployeeShiftAssignment).filter(
        EmployeeShiftAssignment.employee_id == data.employee_id,
        EmployeeShiftAssignment.end_date == None,  # active shift
    ).first()

    if overlapping:
        raise HTTPException(400, "Employee already has active shift")

    assignment = EmployeeShiftAssignment(**data.model_dump())
    assignment.created_by = user.id

    db.add(assignment)
    db.commit()
    db.refresh(assignment)

    return assignment


def change_shift(db: Session, employee_id: int, new_shift_id: int, start_date: date, user):

    current = db.query(EmployeeShiftAssignment).filter(
        EmployeeShiftAssignment.employee_id == employee_id,
        EmployeeShiftAssignment.end_date == None
    ).first()

    if not current:
        raise HTTPException(404, "No active shift found")

    # 🔚 Close current shift
    current.end_date = start_date

    # 🆕 New shift
    new_assignment = EmployeeShiftAssignment(
        employee_id=employee_id,
        shift_id=new_shift_id,
        start_date=start_date,
        created_by=user.id
    )

    db.add(new_assignment)
    db.commit()

    return new_assignment


def get_employee_shift_history(db, employee_id: int, user):

    # 🔒 Validate employee
    employee = db.query(Employee).filter(
        Employee.id == employee_id,
        Employee.deleted_at == None
    ).first()

    if not employee:
        raise HTTPException(404, "Employee not found")

    # 🔒 Access control
    if user.user_type == "employee":
        if employee_id != user.id:
            raise HTTPException(403, "Not allowed")

    elif not is_global_admin(user):
        if employee.company_id != user.company_id:
            raise HTTPException(403, "Not allowed")

    # 📜 Fetch history
    assignments = db.query(EmployeeShiftAssignment).filter(
        EmployeeShiftAssignment.employee_id == employee_id
    ).order_by(EmployeeShiftAssignment.start_date.desc()).all()

    return assignments


def get_current_shift(db, employee_id: int, user):

    # 🔒 Validate employee
    employee = db.query(Employee).filter(
        Employee.id == employee_id,
        Employee.deleted_at == None
    ).first()

    if not employee:
        raise HTTPException(404, "Employee not found")

    # 🔒 Access control
    if user.user_type == "employee":
        if employee_id != user.id:
            raise HTTPException(403, "Not allowed")

    elif not is_global_admin(user):
        if employee.company_id != user.company_id:
            raise HTTPException(403, "Not allowed")

    # 🔍 Get active shift
    assignment = db.query(EmployeeShiftAssignment).filter(
        EmployeeShiftAssignment.employee_id == employee_id,
        EmployeeShiftAssignment.end_date == None
    ).first()

    if not assignment:
        raise HTTPException(404, "No active shift found")

    return assignment