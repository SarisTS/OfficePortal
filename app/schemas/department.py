from pydantic import BaseModel
from typing import Optional


class DepartmentCreate(BaseModel):
    company_id: int
    dept_name: str


class DepartmentUpdate(BaseModel):
    dept_name: Optional[str] = None
    company_id: Optional[int] = None


class DepartmentResponse(BaseModel):
    id: int
    company_id: int
    dept_name: str

    class Config:
        from_attributes = True