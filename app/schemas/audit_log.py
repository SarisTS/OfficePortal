from datetime import datetime
from typing import Any, Optional

from pydantic import BaseModel, ConfigDict


class AuditLogResponse(BaseModel):
    id: int
    actor_id: Optional[int]
    actor_email: Optional[str]
    action: str
    entity_type: str
    entity_id: Optional[int]
    company_id: Optional[int]
    before: Optional[dict[str, Any]]
    after: Optional[dict[str, Any]]
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)


class AuditLogListResponse(BaseModel):
    total: int
    skip: int
    limit: int
    items: list[AuditLogResponse]
