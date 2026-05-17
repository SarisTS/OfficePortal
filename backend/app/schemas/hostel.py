from pydantic import BaseModel, ConfigDict
from typing import Optional

from app.schemas.base import StrictRequestModel


class HostelCreate(StrictRequestModel):

    name: str
    flat_no: Optional[str] = None

    address_line_1: Optional[str] = None
    address_line_2: Optional[str] = None
    landmark: Optional[str] = None

    location_id: Optional[int] = None

    # super_admin can target any company. office_admin should leave this
    # null — the CRUD layer stamps it from their session — and a
    # mismatched value will be rejected with 403.
    company_id: Optional[int] = None


class HostelUpdate(StrictRequestModel):
    name: Optional[str] = None
    flat_no: Optional[str] = None

    address_line_1: Optional[str] = None
    address_line_2: Optional[str] = None
    landmark: Optional[str] = None

    location_id: Optional[int] = None

    # Only super_admin can move a hostel between companies. office_admin
    # supplying a different company_id is refused at the CRUD layer.
    company_id: Optional[int] = None


class HostelResponse(BaseModel):
    id: int
    name: str
    flat_no: Optional[str] = None

    address_line_1: Optional[str] = None
    address_line_2: Optional[str] = None
    landmark: Optional[str] = None

    location_id: Optional[int] = None
    company_id: Optional[int] = None

    model_config = ConfigDict(from_attributes=True)
