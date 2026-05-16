import secrets
import string
from sqlalchemy.orm import Session, joinedload
from app.models.employee import Employee, UserTypes
from app.models.role import Role
from app.models.department import Department
from app.schemas.employee import EmployeeCreate, EmployeeUpdate
from fastapi import HTTPException, BackgroundTasks
from app.crud.auth import is_global_admin
from app.core.logger import get_logger
from app.utils.hash import hash_password
from datetime import datetime, timezone, date
from app.models.assignment import EmployeeShiftAssignment
from app.models.attendance import Shift
from app.core.config import settings
import smtplib
from email.mime.text import MIMEText


logger = get_logger()

def generate_roll_no(db: Session):
    last = db.query(Employee).order_by(Employee.id.desc()).first()

    if not last or not last.roll_no:
        return "RMT001"

    last_number = int(last.roll_no.replace("RMT", ""))
    return f"RMT{last_number + 1:03d}"

def generate_password(length=10):
    chars = string.ascii_letters + string.digits
    return ''.join(secrets.choice(chars) for _ in range(length))


def send_email(to_email: str, subject: str, body: str):
    """
    Send an email using SMTP. Reusable for OTPs, notifications, etc.
    """
    msg = MIMEText(body)
    msg['From'] = settings.EMAIL_HOST_USER
    msg['To'] = to_email
    msg['Subject'] = subject

    with smtplib.SMTP(settings.EMAIL_HOST, settings.EMAIL_PORT) as server:
        if settings.EMAIL_USE_TLS:
            server.starttls()
        server.login(settings.EMAIL_HOST_USER, settings.EMAIL_HOST_PASSWORD)
        server.sendmail(settings.EMAIL_HOST_USER, to_email, msg.as_string())

def send_employee_credentials_email(to, roll_no, password):

    subject = "Your Login Credentials"
    body = f"""
            Welcome to the Company!

            Your login credentials:

            Roll No: {roll_no}
            Password: {password}

            Please change your password after first login.

            Regards,
            Admin Team
            """

    send_email(to, subject, body)
    print("Email: ", to)
    print("Roll No: ", roll_no)
    print("Password: ", password)

    return

def create_employee(db: Session, employee: EmployeeCreate, user, background_tasks: BackgroundTasks):
    try:
        data = employee.model_dump()

        # 🔒 Email uniqueness
        if data.get("email"):
            existing = db.query(Employee).filter(
                Employee.email == data["email"],
                Employee.deleted_at == None
            ).first()
            if existing:
                raise HTTPException(400, "Email already exists")

        # 🔒 Mobile uniqueness
        if data.get("mobile"):
            existing = db.query(Employee).filter(
                Employee.mobile == data["mobile"],
                Employee.deleted_at == None
            ).first()
            if existing:
                raise HTTPException(400, "Mobile already exists")

        # 🔢 Generate roll number
        data["roll_no"] = generate_roll_no(db)

        # 🔐 Password
        plain_password = generate_password()
        data["password_hash"] = hash_password(plain_password)

        # 🔒 Department validation
        if data.get("department_id"):
            dept = db.query(Department).filter(
                Department.id == data["department_id"],
                Department.deleted_at == None
            ).first()

            if not dept:
                raise HTTPException(400, "Invalid department")

            if dept.company_id != data["company_id"]:
                raise HTTPException(400, "Department mismatch")

        # 🔒 Role validation
        role = db.query(Role).filter(Role.id == data["role_id"]).first()
        if not role:
            raise HTTPException(400, "Invalid role")

        # 📍 Clean city
        data["city"] = data["city"].strip().title() if data.get("city") else None

        # 🧱 Create employee
        db_employee = Employee(**data)
        db_employee.created_by = user.id

        db.add(db_employee)
        db.flush()  # ✅ IMPORTANT

        # ✅ SHIFT ASSIGNMENT (correct way)
        shift_id = data.get("shift_id")

        if shift_id:
            shift = db.query(Shift).filter(
                Shift.id == shift_id,
                Shift.company_id == db_employee.company_id
            ).first()

            if not shift:
                raise HTTPException(400, "Invalid shift")

            assignment = EmployeeShiftAssignment(
                employee_id=db_employee.id,
                shift_id=shift_id,
                start_date=date.today(),
                created_by=user.id
            )

            db.add(assignment)

        # ✅ Single commit
        db.commit()
        db.refresh(db_employee)

        # 📧 Send email AFTER commit
        if data.get("email"):
            try:
                background_tasks.add_task(
                    send_employee_credentials_email, 
                    data["email"],
                    db_employee.roll_no,
                    plain_password
                )
            except Exception as e:
                logger.error(f"Email failed: {e}")

        return db_employee

    except Exception as e:
        db.rollback()
        logger.exception("Error creating employee")
        raise e


def get_employee(db: Session, employee_id: int, user):
    employee = (db
                .query(Employee)
                .options(joinedload(Employee.role), joinedload(Employee.department))
                .filter(Employee.id == employee_id, Employee.deleted_at == None)
                .first()
    )

    if not employee:
        return None

    # 🔒 Tenant control
    if not is_global_admin(user):
        if employee.company_id != user.company_id:
            raise HTTPException(403, "Not allowed")

    return {
            "id": employee.id,
            "roll_no": employee.roll_no,
            "name": employee.name,
            "email": employee.email,
            "role_id": employee.role_id,
            "role_name": employee.role.role_name if employee.role else None,
            "user_type": employee.user_type,
            "company_id": employee.company_id,
            "department_id": employee.department_id,
            "department_name": employee.department.dept_name if employee.department else None,
            "hostel_id": employee.hostel_id,
            "mobile": employee.mobile,
            "address_line_1": employee.address_line_1,
            "address_line_2": employee.address_line_2,
            "landmark": employee.landmark,
            "city": employee.city,
            "state": employee.state,
            "pincode": employee.pincode,
            "is_active": employee.is_active,
            "created_at": employee.created_at,
            "updated_at": employee.updated_at,
        }


def get_all_employees(db: Session, user, skip=0, limit=10):
    query = (
        db.query(Employee)
        .options(joinedload(Employee.role), joinedload(Employee.department))
        .filter(Employee.deleted_at == None)
        )

    if not is_global_admin(user):
        query = query.filter(Employee.company_id == user.company_id)

    total = query.count()

    employees = query.order_by(Employee.id.desc()).offset(skip).limit(limit).all()

    items = []
    for emp in employees:
        items.append({
            "id": emp.id,
            "roll_no": emp.roll_no,
            "name": emp.name,
            "email": emp.email,
            "role_id": emp.role_id,
            "role_name": emp.role.role_name if emp.role else None,
            "user_type": emp.user_type,
            "company_id": emp.company_id,
            "department_id": emp.department_id,
            "department_name": emp.department.dept_name if emp.department else None,
            "hostel_id": emp.hostel_id,
            "mobile": emp.mobile,
            "address_line_1": emp.address_line_1,
            "address_line_2": emp.address_line_2,
            "landmark": emp.landmark,
            "city": emp.city,
            "state": emp.state,
            "pincode": emp.pincode,
            "is_active": emp.is_active,
            "created_at": emp.created_at,
            "updated_at": emp.updated_at,
        })

    return {
        "skip": skip,
        "limit": limit,
        "total": total,
        "items": items
    }


def get_employees_by_role(db: Session, user, role_id, skip=0, limit=10):
    query = (
        db.query(Employee)
        .options(joinedload(Employee.role), joinedload(Employee.department))
        .filter(Employee.role_id == role_id, Employee.deleted_at == None)
        )

    if not is_global_admin(user):
        query = query.filter(Employee.company_id == user.company_id)

    total = query.count()

    employees = query.order_by(Employee.id.desc()).offset(skip).limit(limit).all()

    items = []
    for emp in employees:
        items.append({
            "id": emp.id,
            "roll_no": emp.roll_no,
            "name": emp.name,
            "email": emp.email,
            "role_id": emp.role_id,
            "role_name": emp.role.role_name if emp.role else None,
            "user_type": emp.user_type,
            "company_id": emp.company_id,
            "department_id": emp.department_id,
            "department_name": emp.department.dept_name if emp.department else None,
            "hostel_id": emp.hostel_id,
            "mobile": emp.mobile,
            "address_line_1": emp.address_line_1,
            "address_line_2": emp.address_line_2,
            "landmark": emp.landmark,
            "city": emp.city,
            "state": emp.state,
            "pincode": emp.pincode,
            "is_active": emp.is_active,
            "created_at": emp.created_at,
            "updated_at": emp.updated_at,
        })

    return {
        "skip": skip,
        "limit": limit,
        "total": total,
        "items": items
    }


def update_employee(db: Session, employee_id: int, employee: EmployeeUpdate, user):
    try:
        db_employee = db.query(Employee).filter(
            Employee.id == employee_id,
            Employee.deleted_at == None
        ).first()

        if not db_employee:
            return None

        # 🔒 Tenant control
        if not is_global_admin(user):
            if db_employee.company_id != user.company_id:
                raise HTTPException(403, "Not allowed")

        update_data = employee.model_dump(exclude_unset=True)

        # ❌ Prevent critical changes
        if "company_id" in update_data:
            raise HTTPException(400, "Cannot change company")

        if "roll_no" in update_data:
            raise HTTPException(400, "Cannot change roll number")

        if "user_type" in update_data:
            raise HTTPException(403, "Cannot change user type")

        # 🔒 Email uniqueness
        if "email" in update_data:
            existing = db.query(Employee).filter(
                Employee.email == update_data["email"],
                Employee.id != employee_id,
                Employee.deleted_at == None
            ).first()

            if existing:
                raise HTTPException(400, "Email already exists")

        # 🔒 Department validation
        if "department_id" in update_data:
            dept = db.query(Department).filter(
                Department.id == update_data["department_id"],
                Department.deleted_at == None
            ).first()

            if not dept:
                raise HTTPException(400, "Invalid department")

            if dept.company_id != db_employee.company_id:
                raise HTTPException(400, "Department mismatch")

        # 🔒 Role validation
        if "role_id" in update_data:
            role = db.query(Role).filter(Role.id == update_data["role_id"]).first()
            if not role:
                raise HTTPException(400, "Invalid role")

        # 🔄 Apply updates
        for key, value in update_data.items():
            setattr(db_employee, key, value)

        db_employee.updated_by = user.id

        db.commit()
        db.refresh(db_employee)

        return db_employee

    except Exception:
        db.rollback()
        logger.exception("Error updating employee")
        raise



def delete_employee(db: Session, employee_id: int, user):
    try:
        employee = db.query(Employee).filter(
            Employee.id == employee_id,
            Employee.deleted_at == None
        ).first()

        if not employee:
            return None

        # 🔒 Tenant control
        if not is_global_admin(user):
            if employee.company_id != user.company_id:
                raise HTTPException(403, "Not allowed")

        # ❌ Prevent deleting super admin
        if employee.user_type == UserTypes.super_admin:
            raise HTTPException(400, "Cannot delete super admin")

        employee.deleted_at = datetime.now(timezone.utc)
        employee.updated_by = user.id

        db.commit()

        return employee

    except Exception:
        db.rollback()
        logger.exception("Error deleting employee")
        raise


# ---------------------------------------------------------------------------
# Bulk CSV import
# ---------------------------------------------------------------------------

def bulk_import_employees(
    db: Session, csv_text: str, actor, background_tasks: BackgroundTasks,
):
    """Parse CSV text + call create_employee per row.

    Conventions:
      - header row (first line) maps to EmployeeCreate field names
      - unknown columns are ignored (admin convenience)
      - empty cells → None so optional fields take their defaults
      - per-row failures captured in `skipped` rather than aborting:
          - Pydantic validation errors  → row schema error
          - HTTPException from create_employee (duplicate email, etc.)
              → reason as detail string
      - row numbering starts at 2 (row 1 is the header) so the indices
        match what a spreadsheet would display
      - office_admin's company_id is force-stamped from the actor (any
        company_id in the CSV is ignored), matching the bulk-holiday
        pattern. super_admin gets company_id from the CSV as-is.

    Returns (created, skipped). Caller serializes to EmployeeResponse.
    """
    import csv as _csv
    import io as _io
    from pydantic import ValidationError

    from app.crud.auth import is_global_admin

    reader = _csv.DictReader(_io.StringIO(csv_text))
    known_fields = set(EmployeeCreate.model_fields.keys())

    created: list[Employee] = []
    skipped: list[dict] = []

    for row_idx, row in enumerate(reader, start=2):
        # Drop unknown columns; coerce empty strings to None.
        cleaned = {
            k: (v if v != "" else None)
            for k, v in row.items()
            if k in known_fields
        }

        # Tenant scoping: office_admin's CSV company_id is overridden.
        if not is_global_admin(actor):
            cleaned["company_id"] = actor.company_id

        try:
            schema = EmployeeCreate(**cleaned)
        except ValidationError as exc:
            skipped.append({
                "row_number": row_idx,
                # include_context=False drops the `ctx` field which can
                # carry raw exception objects (ValueError from field
                # validators) that Pydantic's JSON serializer can't
                # encode through the response model.
                "errors": exc.errors(include_context=False),
            })
            continue

        try:
            emp = create_employee(db, schema, actor, background_tasks)
            created.append(emp)
        except HTTPException as exc:
            skipped.append({
                "row_number": row_idx,
                "errors": [{"detail": str(exc.detail)}],
            })
        except Exception as exc:  # defensive — bubbled from inner commit
            skipped.append({
                "row_number": row_idx,
                "errors": [{"detail": str(exc)}],
            })

    return created, skipped


def update_own_profile(db: Session, user: Employee, data) -> Employee:
    """Apply a self-service profile edit.

    Only the fields whitelisted in app/schemas/employee.py::ProfileUpdate
    can flow in (extra="forbid" rejects everything else with 422 at parse
    time). On top of that, mobile + email get pre-validated against the
    other-user uniqueness invariant so the response is a friendly 400
    instead of a partial-unique-index violation bubbling from the DB.

    Mobile is stripped of whitespace; email is lowercased + stripped to
    match the convention used in the admin create/login paths.
    """
    update_data = data.model_dump(exclude_unset=True)
    if not update_data:
        return user

    # Normalize + uniqueness-check mobile
    if "mobile" in update_data and update_data["mobile"] is not None:
        new_mobile = update_data["mobile"].strip()
        update_data["mobile"] = new_mobile
        if new_mobile and new_mobile != user.mobile:
            conflict = db.query(Employee).filter(
                Employee.mobile == new_mobile,
                Employee.id != user.id,
                Employee.deleted_at.is_(None),
            ).first()
            if conflict:
                raise HTTPException(400, "Mobile number already in use")

    # Normalize + uniqueness-check email
    if "email" in update_data and update_data["email"] is not None:
        new_email = update_data["email"].lower().strip()
        update_data["email"] = new_email
        if new_email and new_email != user.email:
            conflict = db.query(Employee).filter(
                Employee.email == new_email,
                Employee.id != user.id,
                Employee.deleted_at.is_(None),
            ).first()
            if conflict:
                raise HTTPException(400, "Email already in use")

    try:
        for key, value in update_data.items():
            setattr(user, key, value)
        user.updated_by = user.id
        db.commit()
        db.refresh(user)
        return user
    except Exception:
        db.rollback()
        logger.exception("Error updating own profile")
        raise