from app.database.database import SessionLocal
from app.models.employee import Employee, UserTypes
from app.models.role import Role
from app.utils.hash import hash_password


def create_super_admin():
    db = SessionLocal()

    email = "admin@office.com"
    password = "admin@123"

    try:
        # Normalize email
        email = email.lower().strip()

        # Check if role exists
        role = db.query(Role).filter(Role.role_name == "Super Admin").first()

        if not role:
            role = Role(role_name="Super Admin")
            db.add(role)
            db.commit()
            db.refresh(role)

        # Check if super admin already exists
        existing = db.query(Employee).filter(
            Employee.email == email,
            Employee.deleted_at.is_(None)
        ).first()

        if existing:
            print("Super admin already exists")
            return

        # Create super admin
        admin = Employee(
            name="Super Admin",
            email=email,
            password_hash=hash_password(password),
            user_type=UserTypes.super_admin,
            role_id=role.id,
            is_verified=True,
            company_id=None,   # global user
            mobile=None        # optional
        )

        db.add(admin)
        db.commit()

        print("✅ Super admin created successfully")

    except Exception as e:
        db.rollback()
        print(f"❌ Error creating super admin: {e}")

    finally:
        db.close()


if __name__ == "__main__":
    create_super_admin()