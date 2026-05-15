from fastapi import HTTPException

from app.crud.auth import is_global_admin
from app.models.assignment import EmployeeShiftAssignment
from app.models.employee import Employee, UserTypes

# NOTE: Shift table CRUD (create/get/update/delete) used to live here as
# module-level functions, and assign_shift/change_shift had their own copies
# duplicating the *Service classes in app/services/. The routers always
# called the services/ versions, so the duplicates have been removed in
# Phase 4. This module now only contains the read-side helpers for shift
# assignment history that the assignment router actually calls.


def get_employee_shift_history(db, employee_id: int, user):

    # 🔒 Validate employee
    employee = db.query(Employee).filter(
        Employee.id == employee_id,
        Employee.deleted_at == None
    ).first()

    if not employee:
        raise HTTPException(404, "Employee not found")

    # 🔒 Access control: non-admin can only see their own; office_admin must
    # share company; super_admin is unscoped.
    if user.user_type in (UserTypes.staff, UserTypes.employee):
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

    # 🔒 Access control — same rules as get_employee_shift_history.
    if user.user_type in (UserTypes.staff, UserTypes.employee):
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
