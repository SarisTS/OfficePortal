import hmac
import random
from fastapi import APIRouter, BackgroundTasks, Request, Depends, HTTPException, status
from sqlalchemy.orm import Session
from app.core.logger import get_logger

from app.core.config import settings
from app.core.oauth import oauth
from app.core.security import create_access_token
from app.database.database import get_db
from app.schemas.auth import *
from app.schemas.employee import EmployeeCreate, EmployeeResponse
from app.models.employee import Employee, UserTypes
from app.utils.hash import hash_password, verify_password
from app.crud import employee as employee_crud
from app.crud.auth import get_current_user, require_admin, is_global_admin
from app.core.redis import redis_client
from app.utils.api_response import ApiResponse

logger = get_logger()

router = APIRouter(tags=["Auth"])


# ===================================================================================
#                            ADMIN AUTHENTICATION
# ===================================================================================
# Register
#
# DEPRECATED in Phase 1 stabilization (2026-05-16). The canonical path is
# `POST /employees/`, which:
#   - enforces tenant scoping (office_admin can only create in their own
#     company — this endpoint previously trusted request.company_id without
#     checking the actor's tenant, allowing cross-company creation)
#   - generates roll_no via the central sequence (no admin-supplied roll_no)
#   - hashes a generated password + queues the welcome email
#   - writes an audit log entry
#   - validates role + department belong to the same company
#
# This endpoint is kept callable for backward compatibility but now forwards
# to crud.employee.create_employee with the same safety net. The handler-side
# logic that bypassed all of the above is gone.
@router.post("/employees", response_model=ApiResponse, deprecated=True)
def create_employee(
    request: CreateEmployeeSchema,
    background_tasks: BackgroundTasks,
    current_user: Employee = Depends(require_admin),
    db: Session = Depends(get_db),
):
    # Permission: super_admin can create any role; office_admin can only
    # create staff/employees (never admins).
    if is_global_admin(current_user):
        allowed = [UserTypes.office_admin, UserTypes.staff, UserTypes.employee]
    else:
        allowed = [UserTypes.staff, UserTypes.employee]

    if request.user_type not in allowed:
        raise HTTPException(403, "Cannot create this user type")

    # Tenant force-stamp: office_admin gets pinned to their own company
    # regardless of what request.company_id says. super_admin must supply
    # one (these are staff/employee/office_admin rows that need a company).
    if is_global_admin(current_user):
        company_id = request.company_id
        if not company_id:
            raise HTTPException(400, "company_id required")
    else:
        company_id = current_user.company_id

    if not request.email:
        raise HTTPException(400, "Email required")

    # Translate the auth-side CreateEmployeeSchema into the canonical
    # EmployeeCreate. Fields not present on CreateEmployeeSchema
    # (address, hostel, etc.) fall through as None — admins can fill them
    # later via PUT /employees/{id}.
    payload = EmployeeCreate(
        name=request.name,
        email=request.email,
        company_id=company_id,
        role_id=request.role_id,
        user_type=request.user_type,
        department_id=request.department_id,
        mobile=request.mobile,
    )

    employee = employee_crud.create_employee(
        db, payload, current_user, background_tasks,
    )

    return {
        "status": status.HTTP_200_OK,
        "message": "Employee Created Successfully",
        "data": {
            "id": employee.id,
            "name": employee.name,
            "roll_no": employee.roll_no,
        },
    }

# Admin Login
@router.post("/admin/login", response_model=ApiResponse)
def admin_login(request: LoginRequest, db: Session = Depends(get_db)):
    employee = db.query(Employee).filter(
        Employee.email == request.email,
        Employee.deleted_at.is_(None)
    ).first()

    if not employee or not employee.password_hash:
        raise HTTPException(400, "Invalid credentials")

    if employee.user_type not in [UserTypes.super_admin, UserTypes.office_admin]:
        raise HTTPException(403, "Access denied")

    if not verify_password(request.password, employee.password_hash):
        raise HTTPException(400, "Invalid credentials")

    if not employee.is_active:
        # Deactivated accounts get a clear message so the user knows to
        # contact their admin rather than retrying the password. The
        # admin-side activate/deactivate flow flips this back.
        raise HTTPException(403, "Account is deactivated. Contact your administrator.")

    token = create_access_token({
        "sub": str(employee.id),
        "user_type": employee.user_type.value,
    })

    return {
        "status": status.HTTP_200_OK,
        "message": "Admin Login Successfully",
        "data": {
            "token_type": "bearer",
            "access_token": token
        }
    }

# Google Login
@router.get("/google/login")
async def google_login(request: Request):
    try:
        redirect_uri = request.url_for("google_callback")
        logger.debug(f"Google OAuth redirect_uri={redirect_uri}")

        return await oauth.google.authorize_redirect(
            request,
            redirect_uri
        )

    except Exception:
        logger.exception("Error initiating Google login")
        raise HTTPException(status_code=500, detail="OAuth error")
    

# Google Callback
@router.get("/google/callback", response_model=ApiResponse)
async def google_callback(request: Request, db: Session = Depends(get_db)):
    try:
        token = await oauth.google.authorize_access_token(request)

        user_info = token.get("userinfo")
        if not user_info:
            user_info = await oauth.google.parse_id_token(request, token)

        if not user_info:
            raise HTTPException(status_code=400, detail="Failed to fetch user info")

        email = user_info.get("email")
        google_id = user_info.get("sub")
        email_verified = user_info.get("email_verified")

        if not email or not email_verified:
            raise HTTPException(status_code=400, detail="Invalid or unverified email")

        email = email.lower().strip()

        employee = db.query(Employee).filter(
            (Employee.email == email) | (Employee.google_id == google_id),
            Employee.deleted_at.is_(None)
        ).first()

        if not employee:
            raise HTTPException(400, "User not found")

        if employee.user_type not in [UserTypes.super_admin, UserTypes.office_admin]:
            raise HTTPException(403, "Access denied")

        if not employee.is_active:
            raise HTTPException(403, "Account is deactivated. Contact your administrator.")

        # Link Google
        if not employee.google_id:
            employee.google_id = google_id
            db.commit()

        jwt_token = create_access_token({
            "sub": str(employee.id),
            "email": employee.email,
            "user_type": employee.user_type.value
        })

        return {
            "status": status.HTTP_200_OK,
            "message": "Admin Login via Google OAuth Successfully",
            "data": {
                "token_type": "bearer",
                "access_token": jwt_token
            }
        }

    except HTTPException:
        # Validation errors raised inside the try block (unverified email,
        # access denied, user not found) should reach the client as-is.
        # Previously the generic except below swallowed them into a 500
        # with the message "Google authentication failed", hiding the
        # real reason from the caller.
        raise
    except Exception:
        logger.exception("Google login failed")
        raise HTTPException(status_code=500, detail="Google authentication failed")


# Logout
#
# JWTs are stateless and don't carry server-side session state, so this
# endpoint is intentionally a no-op: the client is expected to discard
# the token on its side. A future Phase 2 refresh-token implementation
# will replace this with real server-side revocation (deny-list or
# token-version on Employee). Keeping the URL stable now means the
# Flutter and Admin React clients can wire the logout button today.
@router.post("/logout", response_model=ApiResponse)
def logout(current_user: Employee = Depends(get_current_user)):
    return {
        "status": status.HTTP_200_OK,
        "message": "Logged out. Discard the token on the client.",
        "data": {},
    }


# Admin Change Password
@router.post("/change-password", response_model=ApiResponse)
def change_password(
    request: ChangePasswordSchema,
    current_user: Employee = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    
    if not current_user.password_hash:
        raise HTTPException(400, "Password not set")
    
    if not verify_password(request.old_password, current_user.password_hash):
        raise HTTPException(400, "Invalid old password")

    current_user.password_hash = hash_password(request.new_password)
    db.commit()

    return {
        "status": status.HTTP_200_OK,
        "message": "Password Updated Successfully",
        "data": {}
    }


    
# ===================================================================================
#                            USER AUTHENTICATION
# ===================================================================================


# Employee Login
@router.post("/employee/login", response_model=ApiResponse)
def employee_login(request: EmployeeLoginSchema, db: Session = Depends(get_db)):
    employee = db.query(Employee).filter(
        Employee.roll_no == request.roll_no,
        Employee.deleted_at.is_(None)
    ).first()

    if not employee or not employee.password_hash:
        raise HTTPException(400, "Invalid credentials")

    if employee.user_type not in [UserTypes.staff, UserTypes.employee]:
        raise HTTPException(403, "Access denied")

    if not verify_password(request.password, employee.password_hash):
        raise HTTPException(400, "Invalid credentials")

    if not employee.is_active:
        raise HTTPException(403, "Account is deactivated. Contact your administrator.")

    token = create_access_token({
        "sub": str(employee.id),
        "user_type": employee.user_type.value,
    })

    return {
        "status": status.HTTP_200_OK,
        "message": "Employee Login Successfully",
        "data": {
            "token_type": "bearer",
            "access_token": token
        }
    }


# Employee Send OTP
@router.post("/send-otp", response_model=ApiResponse)
def send_otp(request: OTPRequestSchema, db: Session = Depends(get_db)):
    employee = db.query(Employee).filter(
        Employee.mobile == request.mobile,
        Employee.deleted_at.is_(None)
    ).first()

    if not employee:
        raise HTTPException(400, "Invalid mobile")

    otp = str(random.randint(100000, 999999))

    redis_client.setex(f"otp:{request.mobile}", 300, otp)

    # TODO: send SMS. In dev only, surface OTP in logs (never in prod).
    if settings.DEBUG:
        logger.debug(f"[dev] OTP for {request.mobile}: {otp}")

    return {
        "status": status.HTTP_200_OK,
        "message": "OTP Sent Successfully",
        "data": {}
    }


# Employee Verify OTP
@router.post("/verify-otp", response_model=ApiResponse)
def verify_otp(request: OTPVerifySchema, db: Session = Depends(get_db)):
    stored_otp = redis_client.get(f"otp:{request.mobile}")

    # redis_client is created with decode_responses=True, so stored_otp is str | None.
    # Constant-time compare to avoid trivial OTP timing oracles.
    if not stored_otp or not hmac.compare_digest(stored_otp, request.otp):
        raise HTTPException(400, "Invalid OTP")

    employee = db.query(Employee).filter(
        Employee.mobile == request.mobile,
        Employee.deleted_at.is_(None)
    ).first()

    if not employee:
        raise HTTPException(400, "User not found")

    if not employee.is_active:
        raise HTTPException(403, "Account is deactivated. Contact your administrator.")

    token = create_access_token({
        "sub": str(employee.id),
        "user_type": employee.user_type.value,
        "company_id": employee.company_id
    })

    redis_client.delete(f"otp:{request.mobile}")

    return {
        "status": status.HTTP_200_OK,
        "message": "OTP Verified Successfully",
        "data": {
            "token_type": "bearer",
            "access_token": token
        }
    }


# Employee Forgot Password
@router.post("/employee/forgot-password", response_model=ApiResponse)
def forgot_password(data: OTPRequestSchema, db: Session = Depends(get_db)):
    employee = db.query(Employee).filter(
        Employee.mobile == data.mobile,
        Employee.deleted_at.is_(None)
    ).first()

    if not employee:
        raise HTTPException(404, "User not found")

    otp = str(random.randint(100000, 999999))

    redis_client.setex(f"reset_otp:{data.mobile}", 300, otp)

    if settings.DEBUG:
        logger.debug(f"[dev] Reset OTP for {data.mobile}: {otp}")

    return {
        "status": status.HTTP_200_OK,
        "message": "OTP Sent for Password reset",
        "data": {}
    }


# Employee Reset Password
@router.post("/employee/reset-password", response_model=ApiResponse)
def reset_password(data: ResetPasswordSchema, db: Session = Depends(get_db)):
    stored_otp = redis_client.get(f"reset_otp:{data.mobile}")

    # decode_responses=True → stored_otp is str | None. Constant-time compare.
    if not stored_otp or not hmac.compare_digest(stored_otp, data.otp):
        raise HTTPException(400, "Invalid or expired OTP")

    employee = db.query(Employee).filter(
        Employee.mobile == data.mobile,
        Employee.deleted_at.is_(None)
    ).first()

    if not employee:
        raise HTTPException(404, "User not found")

    employee.password_hash = hash_password(data.new_password)
    db.commit()

    redis_client.delete(f"reset_otp:{data.mobile}")

    return {
        "status": status.HTTP_200_OK,
        "message": "Password reset Successfully",
        "data": {}
    }

@router.get("/me", response_model=ApiResponse)
def get_me(current_user: Employee = Depends(get_current_user)):
    # Return a Pydantic projection — never the raw ORM object, which would
    # leak password_hash, google_id, and other sensitive columns.
    profile = EmployeeResponse.model_validate(current_user)
    return {
        "status": status.HTTP_200_OK,
        "message": "OK",
        "data": profile.model_dump(),
    }