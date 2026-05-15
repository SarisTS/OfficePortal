from pydantic import BaseModel
from typing import Optional

from app.schemas.base import StrictRequestModel


class CompanyCreate(StrictRequestModel):

    name: str
    email: Optional[str] = None
    phone: Optional[str] = None

    flat_no: Optional[str] = None
    address_line_1: Optional[str] = None
    address_line_2: Optional[str] = None
    landmark: Optional[str] = None

    location_id: Optional[int] = None
    parent_company_id: Optional[int] = None


class CompanyUpdate(StrictRequestModel):

    name: Optional[str] = None
    email: Optional[str] = None
    phone: Optional[str] = None

    flat_no: Optional[str] = None
    address_line_1: Optional[str] = None
    address_line_2: Optional[str] = None
    landmark: Optional[str] = None

    location_id: Optional[int] = None
    parent_company_id: Optional[int] = None


class CompanyResponse(BaseModel):

    id: int
    name: str
    email: Optional[str] = None
    phone: Optional[str] = None

    flat_no: Optional[str] = None
    address_line_1: Optional[str] = None
    address_line_2: Optional[str] = None
    landmark: Optional[str] = None

    location_id: Optional[int] = None
    parent_company_id: Optional[int] = None

    class Config:
        from_attributes = True