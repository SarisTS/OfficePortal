from datetime import date, datetime
from typing import Optional

from pydantic import BaseModel, ConfigDict, field_validator

from app.schemas.base import StrictRequestModel


# ---------- SalaryStructure ----------

_EARNING_FIELDS = (
    "basic", "hra", "special_allowance", "other_allowances",
)
_DEDUCTION_FIELDS = (
    "pf", "professional_tax", "tds", "other_deductions",
)


class SalaryStructureCreate(StrictRequestModel):
    employee_id: int
    effective_from: date

    basic: float = 0
    hra: float = 0
    special_allowance: float = 0
    other_allowances: float = 0

    pf: float = 0
    professional_tax: float = 0
    tds: float = 0
    other_deductions: float = 0

    @field_validator(*_EARNING_FIELDS, *_DEDUCTION_FIELDS)
    def must_be_non_negative(cls, v: float) -> float:
        if v < 0:
            raise ValueError("Amounts must be >= 0")
        return v


class SalaryStructureUpdate(StrictRequestModel):
    """Tweak amounts on an existing structure. effective_from is NOT
    updatable — to change when a structure starts, create a new one."""
    basic: Optional[float] = None
    hra: Optional[float] = None
    special_allowance: Optional[float] = None
    other_allowances: Optional[float] = None

    pf: Optional[float] = None
    professional_tax: Optional[float] = None
    tds: Optional[float] = None
    other_deductions: Optional[float] = None

    @field_validator(*_EARNING_FIELDS, *_DEDUCTION_FIELDS)
    def must_be_non_negative_if_present(cls, v: Optional[float]) -> Optional[float]:
        if v is not None and v < 0:
            raise ValueError("Amounts must be >= 0")
        return v


class SalaryStructureResponse(BaseModel):
    id: int
    employee_id: int
    effective_from: date

    basic: float
    hra: float
    special_allowance: float
    other_allowances: float

    pf: float
    professional_tax: float
    tds: float
    other_deductions: float

    model_config = ConfigDict(from_attributes=True)


# ---------- Payslip ----------

class PayslipResponse(BaseModel):
    id: int
    employee_id: int
    year: int
    month: int

    # Snapshotted at generation time — never recompute.
    basic: float
    hra: float
    special_allowance: float
    other_allowances: float

    pf: float
    professional_tax: float
    tds: float
    other_deductions: float

    gross: float
    total_deductions: float
    net: float

    days_in_period: int
    days_worked: float
    days_lwp: float

    generated_at: datetime

    model_config = ConfigDict(from_attributes=True)
