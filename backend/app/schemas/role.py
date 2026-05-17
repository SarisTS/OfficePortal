from pydantic import BaseModel, ConfigDict
from typing import Optional

from app.schemas.base import StrictRequestModel


class RoleCreate(StrictRequestModel):
    role_name: str


class RoleUpdate(StrictRequestModel):
    role_name: Optional[str] = None


class RoleResponse(BaseModel):
    id: int
    role_name: str

    model_config = ConfigDict(from_attributes=True)