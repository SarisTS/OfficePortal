from app.utils.hash import verify_password
from app.core.security import create_access_token
from app.models.employee import Employee, UserTypes

from fastapi import Depends, HTTPException, status
from fastapi.security import OAuth2PasswordBearer
from jose import jwt
from sqlalchemy.orm import Session

from app.database.database import get_db
from app.core.logger import get_logger
from app.core.config import settings

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
        data={"user_id": user.id}
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
    try:
        payload = jwt.decode(token, settings.SECRET_KEY, algorithms=[settings.ALGORITHM])

        user_id = payload.get("sub")   # 👈 now correct

        if not user_id:
            raise HTTPException(status_code=401, detail="Invalid token")

        user = db.query(Employee).filter(Employee.id == int(user_id)).first()

        if not user:
            raise HTTPException(status_code=401, detail="User not found")

        return user

    except Exception:
        logger.exception("Invalid Token")
        raise HTTPException(status_code=401, detail="Invalid token")
    

def require_admin(user = Depends(get_current_user)):
    if user.user_type not in [UserTypes.super_admin, UserTypes.office_admin]:
        raise HTTPException(status_code=403, detail="Not authorized")
    return user

def require_user(user = Depends(get_current_user)):
    if user.user_type not in [UserTypes.super_admin, UserTypes.office_admin, UserTypes.staff, UserTypes.employee]:
        raise HTTPException(status_code=403, detail="Not authorized")
    return user


def is_global_admin(user):
    return user.user_type in ["super_admin", "office_admin"]