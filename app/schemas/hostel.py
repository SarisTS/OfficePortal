from pydantic import BaseModel
from typing import Optional



class HostelCreate(BaseModel):

    name: str
    flat_no: Optional[str] = None

    address_line_1: Optional[str] = None
    address_line_2: Optional[str] = None
    landmark: Optional[str] = None

    location_id: Optional[int] = None


class HostelUpdate(BaseModel):
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

    class Config:
        from_attributes = True