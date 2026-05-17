"""Authorization helpers — single source of truth for RBAC and tenant scoping.

Conventions used across this module:
- ``actor`` is the logged-in user making the request.
- ``target`` is the resource (employee/leave/etc.) the actor wants to touch.
- ``super_admin`` is global (no company scope). ``office_admin`` is bound to
  their own company. ``staff``/``employee`` can act on themselves only.

Routers should call these helpers BEFORE hitting CRUD/service layers; the
CRUD layer should treat ``actor`` as already-vouched-for context.
"""

from fastapi import HTTPException, status
from sqlalchemy.orm import Session

from app.models.employee import Employee, UserTypes


# ---------------------------------------------------------------------------
# Role predicates
# ---------------------------------------------------------------------------

def is_super_admin(user: Employee) -> bool:
    return user.user_type == UserTypes.super_admin


def is_office_admin(user: Employee) -> bool:
    return user.user_type == UserTypes.office_admin


def is_any_admin(user: Employee) -> bool:
    return user.user_type in (UserTypes.super_admin, UserTypes.office_admin)


# ---------------------------------------------------------------------------
# Tenant scope
# ---------------------------------------------------------------------------

def same_company(actor: Employee, target_company_id: int | None) -> bool:
    """True iff the actor is global OR shares the target's company."""
    if is_super_admin(actor):
        return True
    if actor.company_id is None or target_company_id is None:
        return False
    return actor.company_id == target_company_id


def assert_same_company(actor: Employee, target_company_id: int | None) -> None:
    """Raise 403 if the actor cannot act within the target's company."""
    if not same_company(actor, target_company_id):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Resource is outside your company scope",
        )


# ---------------------------------------------------------------------------
# Employee-resource helpers
# ---------------------------------------------------------------------------

def load_employee_or_404(db: Session, employee_id: int) -> Employee:
    employee = (
        db.query(Employee)
        .filter(Employee.id == employee_id, Employee.deleted_at.is_(None))
        .first()
    )
    if not employee:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Employee not found",
        )
    return employee


def assert_self_or_admin(actor: Employee, target_employee_id: int) -> None:
    """Quick role gate for endpoints keyed by employee_id.

    The actor is allowed if they ARE the target, or if they're any admin.
    For admins, the caller still must run ``assert_same_company`` against
    the target's company_id (that needs a DB lookup, so it lives separately).
    """
    if actor.id == target_employee_id:
        return
    if not is_any_admin(actor):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="You can only access your own records",
        )


def assert_can_access_employee(
    db: Session, target_employee_id: int, actor: Employee
) -> Employee:
    """Fetch the target employee, then enforce the full access rule:

        super_admin  → any employee
        office_admin → employees in same company
        staff/employee → only themselves
    """
    if actor.id == target_employee_id:
        return load_employee_or_404(db, target_employee_id)

    if not is_any_admin(actor):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="You can only access your own records",
        )

    target = load_employee_or_404(db, target_employee_id)
    assert_same_company(actor, target.company_id)
    return target
