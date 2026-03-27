from pydantic import BaseModel, EmailStr
from typing import Optional
from app.models.employee import UserTypes

class RegisterRequest(BaseModel):
    email: EmailStr
    password: str
    user_type: str
    role_id: int


class LoginRequest(BaseModel):
    email: EmailStr
    password: str


class ChangePasswordSchema(BaseModel):
    old_password: str
    new_password: str


class ForgotPasswordRequest(BaseModel):
    email: EmailStr


class ResetPasswordRequest(BaseModel):
    token: str
    new_password: str

class TokenResponse(BaseModel):
    access_token: str
    token_type: str

class EmployeeLoginSchema(BaseModel):
    roll_no: str
    password: str

class OTPRequestSchema(BaseModel):
    mobile: str

class OTPVerifySchema(BaseModel):
    mobile: str
    otp: str

class ResetPasswordSchema(BaseModel):
    mobile: str
    otp: str
    new_password: str

class CreateEmployeeSchema(BaseModel):
    name: str
    user_type: UserTypes

    email: Optional[str] = None
    password: Optional[str] = None

    roll_no: Optional[str] = None
    mobile: Optional[str] = None

    company_id: Optional[int] = None
    department_id: Optional[int] = None
    role_id: int