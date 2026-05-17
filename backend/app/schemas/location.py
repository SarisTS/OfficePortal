from pydantic import BaseModel, ConfigDict, Field
from typing import Optional
from datetime import datetime

from app.schemas.base import StrictRequestModel

# ==============================
#   LOCATION SCHEMAS
# ==============================

class LocationBase(BaseModel):
    country_id  : Optional[int] = None
    state_id    : Optional[int] = None
    city_id     : Optional[int] = None
    postal_code : Optional[str] = None
    is_active   : bool = True


class LocationCreate(StrictRequestModel):
    country_id  : int
    state_id    : int
    city_id     : int
    # Postal codes are strings worldwide (alphanumeric in UK/CA/etc., leading
    # zeros must be preserved e.g. "01001"). Was previously typed as int,
    # which silently disagreed with the CRUD layer treating it as str.
    postal_code : Optional[str] = None


class LocationUpdate(StrictRequestModel):
    country_id  : Optional[int]  = None
    state_id    : Optional[int]  = None
    city_id     : Optional[int]  = None
    postal_code : Optional[str]  = None
    is_active   : Optional[bool] = True


class LocationOut(BaseModel):
    id          : int
    country_id  : int
    state_id    : int
    city_id     : int
    country_name: str
    state_name  : str
    city_name   : str
    postal_code : Optional[str]
    is_active   : Optional[bool] = True
    is_deleted  : Optional[bool] = False
    created_at  : Optional[datetime]
    updated_at  : Optional[datetime]
    deleted_at  : Optional[datetime] = None

    model_config = ConfigDict(from_attributes=True)

# ==============================
#   COUNTRY SCHEMAS
# ==============================

class CountryBase(BaseModel):
    name      : str
    code      : str
    phone_code: Optional[str] = None
    is_active : bool = True

class CountryCreate(CountryBase, StrictRequestModel):
    pass

class CountryUpdate(CountryBase, StrictRequestModel):
    pass

class CountryOut(BaseModel):
    id        : int
    name      : str
    code      : str
    phone_code: Optional[str]
    is_active : Optional[bool] = True
    created_at: Optional[datetime]
    updated_at: Optional[datetime]
    deleted_at: Optional[datetime]

    model_config = ConfigDict(from_attributes=True)

class JSONCountryResponse(BaseModel):
    id             : int
    name           : str
    iso3           : Optional[str] = None
    phonecode      : Optional [str] = None
    currency       : Optional [str] = None
    currency_name  : Optional [str] = None
    currency_symbol: Optional [str] = None

    model_config = ConfigDict(from_attributes=True)

# ==============================
#   STATE SCHEMAS
# ==============================

class StateBase(BaseModel):
    name      : str
    code      : str
    country_id: int
    is_active : bool = True

class StateCreate(StateBase, StrictRequestModel):
    pass

class StateUpdate(StateBase, StrictRequestModel):
    pass

class StateOut(BaseModel):
    id        : int
    country_id: int
    name      : str
    code      : Optional[str]
    is_active : Optional[bool] = True
    created_at: Optional[datetime]
    updated_at: Optional[datetime]
    deleted_at: Optional[datetime]

    model_config = ConfigDict(from_attributes=True)

class JSONStateResponse(BaseModel):
    id: int
    name: str
    iso2:Optional[str] = None
    latitude : Optional [str] = None
    longitude : Optional [str] = None
    type: Optional[str] = None

    model_config = ConfigDict(from_attributes=True)

# ==============================
#   CITY SCHEMAS
# ==============================

class CityBase(BaseModel):
    name       : str
    postal_code: str
    state_id   : int
    is_active  : bool = True


class CityCreate(CityBase, StrictRequestModel):
    pass

class CityUpdate(CityBase, StrictRequestModel):
    pass

class CityOut(BaseModel):
    id         : int
    state_id   : int
    name       : str
    postal_code: Optional[str]
    is_active  : Optional[bool] = True
    created_at : Optional[datetime]
    updated_at : Optional[datetime]
    deleted_at : Optional[datetime]

    model_config = ConfigDict(from_attributes=True)

class JSONCityResponse(BaseModel):
    id: int
    name: str
    latitude : Optional [str] = None
    longitude : Optional [str] = None

    model_config = ConfigDict(from_attributes=True)

class UserLocationOut(BaseModel):
    id          : int
    country_id  : int
    state_id    : int
    city_id     : int
    country_name: str
    state_name  : str
    city_name   : str
    postal_code : Optional[str]

    model_config = ConfigDict(from_attributes=True)

# ==============================
#   COMPANY LOCATION LAT LON
# ==============================


class CompanyLocationBase(BaseModel):
    name: str
    latitude: float = Field(..., ge=-90, le=90)
    longitude: float = Field(..., ge=-180, le=180)
    radius: int = Field(default=100, gt=0)
    is_primary: bool


class CompanyLocationCreate(CompanyLocationBase, StrictRequestModel):
    company_id: int


class CompanyLocationUpdate(StrictRequestModel):
    name: Optional[str] = None
    latitude: Optional[float] = Field(default=None, ge=-90, le=90)
    longitude: Optional[float] = Field(default=None, ge=-180, le=180)
    radius: Optional[int] = Field(default=None, gt=0)
    is_active: Optional[bool] = None
    is_primary: Optional[bool] = None


class CompanyLocationResponse(CompanyLocationBase):
    id: int
    company_id: int
    is_active: bool
    is_primary: bool

    model_config = ConfigDict(from_attributes=True)
