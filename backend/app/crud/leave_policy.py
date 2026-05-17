"""CRUD for LeavePolicy.

Admin-only. office_admin can manage policies for their own company;
super_admin can manage any company's policy.
"""
from datetime import datetime, timezone

from fastapi import HTTPException
from sqlalchemy.orm import Session

from app.core.permissions import is_super_admin, same_company
from app.database.database import with_transaction
from app.models.leave import LeavePolicy, LeaveType


def _assert_can_touch_company(actor, target_company_id: int) -> None:
    """office_admin must share company; super_admin is unscoped."""
    if not same_company(actor, target_company_id):
        raise HTTPException(403, "Cannot manage policies for another company")


def create_leave_policy(db: Session, data, actor) -> LeavePolicy:
    _assert_can_touch_company(actor, data.company_id)

    existing = (
        db.query(LeavePolicy)
        .filter(
            LeavePolicy.company_id == data.company_id,
            LeavePolicy.leave_type == data.leave_type,
            LeavePolicy.deleted_at.is_(None),
        )
        .first()
    )
    if existing:
        raise HTTPException(
            400,
            f"A policy for {data.leave_type.value} leave already exists "
            f"in this company. Update it instead.",
        )

    policy = LeavePolicy(
        company_id=data.company_id,
        leave_type=data.leave_type,
        annual_entitlement=data.annual_entitlement,
        created_by=actor.id,
    )
    with with_transaction(db):
        db.add(policy)
    db.refresh(policy)
    return policy


def list_leave_policies(
    db: Session, actor, skip: int = 0, limit: int = 50
):
    base = db.query(LeavePolicy).filter(LeavePolicy.deleted_at.is_(None))
    if not is_super_admin(actor):
        base = base.filter(LeavePolicy.company_id == actor.company_id)

    total = base.count()
    items = base.order_by(LeavePolicy.id).offset(skip).limit(limit).all()
    return total, items


def get_leave_policy(db: Session, policy_id: int, actor) -> LeavePolicy:
    policy = (
        db.query(LeavePolicy)
        .filter(
            LeavePolicy.id == policy_id,
            LeavePolicy.deleted_at.is_(None),
        )
        .first()
    )
    if not policy:
        raise HTTPException(404, "Leave policy not found")

    _assert_can_touch_company(actor, policy.company_id)
    return policy


def update_leave_policy(db: Session, policy_id: int, data, actor) -> LeavePolicy:
    policy = get_leave_policy(db, policy_id, actor)
    with with_transaction(db):
        policy.annual_entitlement = data.annual_entitlement
        policy.updated_by = actor.id
    db.refresh(policy)
    return policy


def delete_leave_policy(db: Session, policy_id: int, actor) -> LeavePolicy:
    policy = get_leave_policy(db, policy_id, actor)
    with with_transaction(db):
        policy.deleted_at = datetime.now(timezone.utc)
        policy.updated_by = actor.id
    return policy
