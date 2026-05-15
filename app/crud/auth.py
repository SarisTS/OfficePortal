from app.utils.hash import verify_password
from app.core.security import create_access_token, verify_access_token
from app.models.employee import Employee, UserTypes

from fastapi import Depends, HTTPException, status
from fastapi.security import OAuth2PasswordBearer
from sqlalchemy.orm import Session

from app.database.database import get_db
from app.core.logger import get_logger

logger = get_logger()


def login_user(email: str, password: str, db: Session):

    user = db.query(Employee).filter(Employee.email == email).first()

    if not user:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid email or password"
        )

    if not verify_password(password, user.password_hash):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid email or password"
        )

    token = create_access_token(
        data={"sub": str(user.id)}
    )

    return {
        "access_token": token,
        "token_type": "bearer"
    }

oauth2_scheme = OAuth2PasswordBearer(tokenUrl="login")


def get_current_user(
    token: str = Depends(oauth2_scheme),
    db: Session = Depends(get_db)
):
    payload = verify_access_token(token)

    user_id = payload.get("sub")
    if not user_id:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid token: missing subject",
            headers={"WWW-Authenticate": "Bearer"},
        )

    try:
        user_id_int = int(user_id)
    except (TypeError, ValueError):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid token: malformed subject",
            headers={"WWW-Authenticate": "Bearer"},
        )

    user = (
        db.query(Employee)
        .filter(Employee.id == user_id_int, Employee.deleted_at.is_(None))
        .first()
    )
    if not user:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="User not found or deactivated",
            headers={"WWW-Authenticate": "Bearer"},
        )

    return user


def require_admin(user = Depends(get_current_user)):
    if user.user_type not in [UserTypes.super_admin, UserTypes.office_admin]:
        raise HTTPException(status_code=403, detail="Not authorized")
    return user

def require_user(user = Depends(get_current_user)):
    if user.user_type not in [UserTypes.super_admin, UserTypes.office_admin, UserTypes.staff, UserTypes.employee]:
        raise HTTPException(status_code=403, detail="Not authorized")
    return user


def is_global_admin(user) -> bool:
    # NOTE: this comparison is currently broken — user.user_type is a UserTypes
    # enum and these are bare strings, so this always returns False. The whole
    # CRUD/service layer has been operating with super_admins silently treated
    # as company-scoped users. Fixing it flips authorization scope across ~10
    # call sites, so it is deliberately left as-is until Phase 2 (RBAC pass).
    # See chore/backend-hardening Phase 1b commit message for context.
    return user.user_type in ["super_admin", "office_admin"]
