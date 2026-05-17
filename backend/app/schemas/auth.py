from pydantic import BaseModel, EmailStr
from typing import Optional

from app.models.employee import UserTypes
from app.schemas.base import StrictRequestModel


class RegisterRequest(StrictRequestModel):
    email: EmailStr
    password: str
    user_type: str
    role_id: int


class LoginRequest(StrictRequestModel):
    email: EmailStr
    password: str


class ChangePasswordSchema(StrictRequestModel):
    old_password: str
    new_password: str


class ForgotPasswordRequest(StrictRequestModel):
    email: EmailStr


class ResetPasswordRequest(StrictRequestModel):
    token: str
    new_password: str


class TokenResponse(BaseModel):
    access_token: str
    token_type: str


class EmployeeLoginSchema(StrictRequestModel):
    roll_no: str
    password: str


class OTPRequestSchema(StrictRequestModel):
    mobile: str


class OTPVerifySchema(StrictRequestModel):
    mobile: str
    otp: str


class ResetPasswordSchema(StrictRequestModel):
    mobile: str
    otp: str
    new_password: str


class CreateEmployeeSchema(StrictRequestModel):
    name: str
    user_type: UserTypes

    email: Optional[str] = None
    password: Optional[str] = None

    roll_no: Optional[str] = None
    mobile: Optional[str] = None

    company_id: Optional[int] = None
    department_id: Optional[int] = None
    role_id: int
