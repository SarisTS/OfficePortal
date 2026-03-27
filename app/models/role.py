from sqlalchemy import Column, Integer, String
from sqlalchemy.orm import relationship
from app.database.base import Base
from app.models.base import AuditMixin

class Role(Base, AuditMixin):
    __tablename__ = "roles"

    id = Column(Integer, primary_key=True)
    role_name = Column(String(100), nullable=False, unique=True)

    employees = relationship("Employee", back_populates="role")