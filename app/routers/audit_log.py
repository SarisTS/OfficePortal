"""Read-only audit log endpoints.

Admin-gated by `require_admin`; tenant scoping (super_admin sees all,
office_admin sees their company) is enforced in crud/audit_log.py so the
router stays thin.

Filterable by actor_id, entity_type, entity_id, action, date range.
Paginated. Sorted newest-first.
"""
from datetime import date

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.orm import Session

from app.crud import audit_log as crud
from app.crud.auth import require_admin
from app.database.database import get_db
from app.schemas.audit_log import AuditLogListResponse, AuditLogResponse
from app.utils.api_response import ApiResponse

router = APIRouter(tags=["Audit Logs"])


@router.get("/", response_model=ApiResponse[AuditLogListResponse])
def list_logs(
    actor_id: int | None = Query(None),
    entity_type: str | None = Query(None),
    entity_id: int | None = Query(None),
    action: str | None = Query(None),
    from_date: date | None = Query(None),
    to_date: date | None = Query(None),
    skip: int = Query(0, ge=0),
    limit: int = Query(50, ge=1, le=200),
    db: Session = Depends(get_db),
    user=Depends(require_admin),
):
    total, items = crud.list_audit_logs(
        db, user,
        actor_id=actor_id, entity_type=entity_type, entity_id=entity_id,
        action=action, from_date=from_date, to_date=to_date,
        skip=skip, limit=limit,
    )
    return {
        "status": status.HTTP_200_OK,
        "message": "Audit logs fetched",
        "data": {
            "total": total,
            "skip": skip,
            "limit": limit,
            "items": items,
        },
    }


@router.get(
    "/{log_id}", response_model=ApiResponse[AuditLogResponse]
)
def get_log(
    log_id: int,
    db: Session = Depends(get_db),
    user=Depends(require_admin),
):
    log = crud.get_audit_log(db, log_id, user)
    if log is None:
        # 404 (not 403) for cross-tenant access too — leaking existence
        # would let an admin probe other companies' audit ID ranges.
        raise HTTPException(404, "Audit log not found")
    return {
        "status": status.HTTP_200_OK,
        "message": "Audit log fetched",
        "data": log,
    }
