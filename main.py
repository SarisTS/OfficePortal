import time
import uuid

from fastapi import FastAPI, Request, HTTPException, Depends
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from sqlalchemy import text
from sqlalchemy.orm import Session
from starlette.middleware.sessions import SessionMiddleware

from app.core.logger import get_logger
from app.core.config import settings
from app.core.redis import redis_client
from app.database.database import get_db

from app.routers.auth import router as auth_router
from app.routers.employee import router as employee_router
from app.routers.attendance import router as attendance_router
from app.routers.company import router as company_router
from app.routers.leave import router as leave_router
from app.routers.leave_policy import router as leave_policy_router
from app.routers.leave_balance import router as leave_balance_router
from app.routers.me import router as me_router
from app.routers.salary_structure import router as salary_structure_router
from app.routers.payslip import router as payslip_router
from app.routers.reports import router as reports_router
from app.routers.holiday import router as holiday_router
from app.routers.admin_food import router as admin_food_router
from app.routers.employee_food import router as employee_food_router
from app.routers.hostel import router as hostel_router
from app.routers.role import router as role_router
from app.routers.department import router as department_router
from app.routers.location import router as location_router
from app.routers.shift import router as shift_router
from app.routers.assignment import router as assignment_router
from app.routers.company_location import router as company_location_router

logger = get_logger()

app = FastAPI()


# Session
app.add_middleware(
    SessionMiddleware,
    secret_key=settings.SECRET_KEY,
    max_age=3600,
    same_site="lax",
    https_only=False
)

# CORS — env-driven allowlist. "*" + allow_credentials=True is rejected by
# browsers, so when wildcard is configured we drop credentials to keep the
# preflight valid (and warn loudly because that combination is a smell).
_cors_origins = [o.strip() for o in settings.CORS_ORIGINS.split(",") if o.strip()]
if not _cors_origins:
    _cors_origins = ["http://localhost:3000"]

if "*" in _cors_origins:
    logger.warning(
        "CORS_ORIGINS contains '*' — disabling allow_credentials. "
        "Configure an explicit origin list before production."
    )
    _allow_credentials = False
else:
    _allow_credentials = True

app.add_middleware(
    CORSMiddleware,
    allow_origins=_cors_origins,
    allow_credentials=_allow_credentials,
    allow_methods=["*"],
    allow_headers=["*"],
)


# Request-id + access log. Mints a UUID per request (or trusts an inbound
# X-Request-ID if the caller sent one — useful for client/server log
# correlation in CI or when an upstream proxy already set it). Stashes it on
# request.state and binds it to loguru's context so every log statement
# emitted inside the request includes it.
@app.middleware("http")
async def request_id_middleware(request: Request, call_next):
    incoming = request.headers.get("X-Request-ID")
    request_id = incoming if incoming else uuid.uuid4().hex
    request.state.request_id = request_id

    start = time.perf_counter()
    with logger.contextualize(request_id=request_id):
        logger.info(f"--> {request.method} {request.url.path}")
        try:
            response = await call_next(request)
        except Exception:
            logger.exception("Unhandled error")
            raise
        elapsed_ms = round((time.perf_counter() - start) * 1000, 2)
        logger.info(
            f"<-- {request.method} {request.url.path} "
            f"{response.status_code} ({elapsed_ms}ms)"
        )
        response.headers["X-Request-ID"] = request_id
        return response

# Error Response
@app.exception_handler(HTTPException)
async def custom_http_exception_handler(request: Request, exc: HTTPException):
    return JSONResponse(
        status_code=exc.status_code,
        content={
            "status": "error",
            "code": exc.status_code,
            "message": exc.detail,
        },
    )

@app.exception_handler(Exception)
async def global_exception_handler(request: Request, exc: Exception):
    return JSONResponse(
        status_code=500,
        content={
            "status": "error",
            "code": 500,
            "message": "Internal Server Error",
        },
    )

# Root
@app.get("/")
def root():
    return {
        "status": "success",
        "message": "API is running",
        "data": None
    }


# Liveness + readiness: DB is required, Redis is best-effort (used for OTPs only).
@app.get("/health")
def health(db: Session = Depends(get_db)):
    db_ok = True
    db_error = None
    try:
        db.execute(text("SELECT 1"))
    except Exception as e:
        db_ok = False
        db_error = str(e)
        logger.exception("Healthcheck: DB ping failed")

    redis_ok = True
    redis_error = None
    try:
        redis_client.ping()
    except Exception as e:
        redis_ok = False
        redis_error = str(e)
        logger.warning(f"Healthcheck: Redis ping failed: {e}")

    body = {
        "status": "ok" if db_ok else "degraded",
        "checks": {
            "database": {"ok": db_ok, "error": db_error},
            "redis": {"ok": redis_ok, "error": redis_error},
        },
        "environment": settings.APP_ENVIRONMENT,
    }
    return JSONResponse(status_code=200 if db_ok else 503, content=body)


# Routers
app.include_router(auth_router, prefix="/auth")
app.include_router(employee_router, prefix="/employees")
app.include_router(attendance_router, prefix="/attendance")
app.include_router(company_router, prefix="/companies")
app.include_router(leave_router, prefix="/leave")
app.include_router(leave_policy_router, prefix="/leave-policies")
app.include_router(leave_balance_router, prefix="/leave-balances")
app.include_router(me_router, prefix="/me")
app.include_router(salary_structure_router, prefix="/salary-structures")
app.include_router(payslip_router, prefix="/payslips")
app.include_router(reports_router, prefix="/reports")
app.include_router(holiday_router, prefix="/company-holidays")
app.include_router(admin_food_router, prefix="/admin/food")
app.include_router(employee_food_router, prefix="/employee/food")
app.include_router(hostel_router, prefix="/hostels")
app.include_router(role_router, prefix="/roles")
app.include_router(department_router, prefix="/departments")
app.include_router(location_router, prefix="/locations")
app.include_router(shift_router, prefix="/shifts")
app.include_router(assignment_router, prefix="/shift-assignments")
app.include_router(company_location_router, prefix="/company-locations")