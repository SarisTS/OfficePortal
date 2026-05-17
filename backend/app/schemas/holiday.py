from datetime import date
from typing import Optional

from pydantic import BaseModel, ConfigDict, field_validator

from app.schemas.base import StrictRequestModel


class CompanyHolidayCreate(StrictRequestModel):
    company_id: int
    date: date
    name: str

    @field_validator("name")
    def name_non_empty(cls, v: str) -> str:
        if not v or not v.strip():
            raise ValueError("name is required")
        return v.strip()


class CompanyHolidayUpdate(StrictRequestModel):
    """Either field is optional. Changing the date may collide with
    another holiday in the same company — the unique-key check in CRUD
    surfaces a friendly 400 in that case."""
    date: Optional[date] = None
    name: Optional[str] = None

    @field_validator("name")
    def name_non_empty_if_present(cls, v):
        if v is not None and not v.strip():
            raise ValueError("name cannot be empty")
        return v.strip() if v else v


class CompanyHolidayResponse(BaseModel):
    id: int
    company_id: int
    date: date
    name: str

    model_config = ConfigDict(from_attributes=True)


# ---------- Bulk create ----------

class HolidayItem(StrictRequestModel):
    """One holiday inside a bulk request."""
    date: date
    name: str

    @field_validator("name")
    def name_non_empty(cls, v: str) -> str:
        if not v or not v.strip():
            raise ValueError("name is required")
        return v.strip()


class CompanyHolidayBulkCreate(StrictRequestModel):
    """Create many holidays in one call — typical use is uploading
    a year's worth at once. Partial failures are reported per-row
    (matches the bulk-payslip-generate pattern)."""
    company_id: int
    holidays: list[HolidayItem]


class CompanyHolidayBulkResult(BaseModel):
    """Response shape for POST /company-holidays/bulk."""
    created: list[CompanyHolidayResponse]
    skipped: list[dict]  # [{"date": "...", "reason": "..."}]


class CompanyHolidayBulkDelete(StrictRequestModel):
    """Body shape for DELETE /company-holidays/bulk.

    Two modes (mutually exclusive — caller picks one):
      - `ids`: delete the listed holiday IDs (precise surgical removal)
      - `year`: delete every holiday in the company for that calendar year
                (typical use: clear a wrong year's import to re-upload)
    """
    company_id: int
    ids: Optional[list[int]] = None
    year: Optional[int] = None


class CompanyHolidayBulkDeleteResult(BaseModel):
    """Response shape for DELETE /company-holidays/bulk."""
    deleted: int
    skipped: list[dict]  # [{"id": int, "reason": str}]


# ---------- Weekly Off ----------

class CompanyWeeklyOffCreate(StrictRequestModel):
    """Mark a weekday as non-working for the company.

    day_of_week follows Python's date.weekday(): 0=Monday, 6=Sunday.
    """
    company_id: int
    day_of_week: int

    @field_validator("day_of_week")
    def day_in_range(cls, v: int) -> int:
        if not 0 <= v <= 6:
            raise ValueError("day_of_week must be in 0..6 (0=Monday, 6=Sunday)")
        return v


class CompanyWeeklyOffResponse(BaseModel):
    id: int
    company_id: int
    day_of_week: int

    model_config = ConfigDict(from_attributes=True)
