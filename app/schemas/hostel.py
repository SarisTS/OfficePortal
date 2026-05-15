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


class HostelUpdate(StrictRequestModel):
    name: Optional[str] = None
    flat_no: Optional[str] = None

    address_line_1: Optional[str] = None
    address_line_2: Optional[str] = None
    landmark: Optional[str] = None

    location_id: Optional[int] = None


class HostelResponse(BaseModel):
    id: int
    name: str
    flat_no: Optional[str] = None

    address_line_1: Optional[str] = None
    address_line_2: Optional[str] = None
    landmark: Optional[str] = None

    location_id: Optional[int] = None

    model_config = ConfigDict(from_attributes=True)