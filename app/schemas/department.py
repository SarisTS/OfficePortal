from pydantic import BaseModel
from typing import Optional

from app.schemas.base import StrictRequestModel


class DepartmentCreate(StrictRequestModel):
    company_id: int
    dept_name: str


class DepartmentUpdate(StrictRequestModel):
    dept_name: Optional[str] = None
    company_id: Optional[int] = None


class DepartmentResponse(BaseModel):
    id: int
    company_id: int
    dept_name: str

    class Config:
        from_attributes = True