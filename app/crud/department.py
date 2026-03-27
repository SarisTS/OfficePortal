from datetime import datetime, timezone
from fastapi import HTTPException

from app.models.department import Department
from app.core.logger import get_logger
from app.crud.auth import is_global_admin

logger = get_logger()


def create_department(db, department, user):
    try:
        # 🔒 Duplicate check
        existing = db.query(Department).filter(
            Department.dept_name == department.dept_name,
            Department.company_id == department.company_id,
            Department.deleted_at == None
        ).first()

        if existing:
            raise HTTPException(400, "Department already exists")

        db_department = Department(**department.model_dump())
        db_department.created_by = user.id

        db.add(db_department)
        db.commit()
        db.refresh(db_department)

        logger.info(f"Department created: {db_department.id}")

        return db_department

    except Exception:
        db.rollback()
        logger.exception("Error creating department")
        raise


def get_departments(db, user, skip=0, limit=10):
    query = db.query(Department).filter(Department.deleted_at == None)

    if not is_global_admin(user):
        query = query.filter(Department.company_id == user.company_id)

    return query.offset(skip).limit(limit).all()


def get_company_departments(db, company_id, user):
    query = db.query(Department).filter(
        Department.company_id == company_id,
        Department.deleted_at == None
    )

    if not is_global_admin(user):
        if company_id != user.company_id:
            raise HTTPException(403, "Not allowed")

    return query.all()


def update_department(db, department_id, data, user):
    try:
        dept = db.query(Department).filter(
            Department.id == department_id,
            Department.deleted_at == None
        ).first()

        if not dept:
            return None

        # 🔒 Access control
        if not is_global_admin(user) and dept.company_id != user.company_id:
            raise HTTPException(403, "Not allowed")

        update_data = data.model_dump(exclude_unset=True)

        # ❌ Prevent company change
        if "company_id" in update_data:
            raise HTTPException(400, "Cannot change company")

        # 🔒 Duplicate check
        if "dept_name" in update_data:
            existing = db.query(Department).filter(
                Department.dept_name == update_data["dept_name"],
                Department.company_id == dept.company_id,
                Department.id != department_id,
                Department.deleted_at == None
            ).first()

            if existing:
                raise HTTPException(400, "Department already exists")

        for key, value in update_data.items():
            setattr(dept, key, value)

        dept.updated_by = user.id

        db.commit()
        db.refresh(dept)

        return dept

    except Exception:
        db.rollback()
        logger.exception("Error updating department")
        raise


def delete_department(db, department_id, user):
    try:
        dept = db.query(Department).filter(
            Department.id == department_id,
            Department.deleted_at == None
        ).first()

        if not dept:
            return None

        if not is_global_admin(user) and dept.company_id != user.company_id:
            raise HTTPException(403, "Not allowed")

        dept.deleted_at = datetime.now(timezone.utc)
        dept.updated_by = user.id

        db.commit()

        return dept

    except Exception:
        db.rollback()
        logger.exception("Error deleting department")
        raise

