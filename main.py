from fastapi import FastAPI, Request, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from starlette.middleware.sessions import SessionMiddleware

from app.core.logger import get_logger
from app.core.config import settings

from app.routers.auth import router as auth_router
from app.routers.employee import router as employee_router
from app.routers.attendance import router as attendance_router
from app.routers.company import router as company_router
from app.routers.leave import router as leave_router
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

# CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # change in production
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# Logging
@app.middleware("http")
async def log_requests(request: Request, call_next):
    logger.info(f"{request.method} {request.url}")

    try:
        response = await call_next(request)
        logger.info(f"Status: {response.status_code}")
        return response
    except Exception:
        logger.exception("Unhandled error")
        raise

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


# Routers
app.include_router(auth_router, prefix="/auth")
app.include_router(employee_router, prefix="/employees")
app.include_router(attendance_router, prefix="/attendance")
app.include_router(company_router, prefix="/companies")
app.include_router(leave_router, prefix="/leave")
app.include_router(admin_food_router, prefix="/admin/food")
app.include_router(employee_food_router, prefix="/employee/food")
app.include_router(hostel_router, prefix="/hostels")
app.include_router(role_router, prefix="/roles")
app.include_router(department_router, prefix="/departments")
app.include_router(location_router, prefix="/locations")
app.include_router(shift_router, prefix="/shifts")
app.include_router(assignment_router, prefix="/shift-assignments")
app.include_router(company_location_router, prefix="/company-locations")