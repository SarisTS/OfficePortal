from sqlalchemy import Column, Integer, String, ForeignKey, UniqueConstraint
from sqlalchemy.orm import relationship
from app.database.base import Base
from app.models.base import AuditMixin


class Department(Base, AuditMixin):
    __tablename__ = "departments"

    id = Column(Integer, primary_key=True)

    dept_name = Column(String(100), nullable=False)

    company_id = Column(Integer, ForeignKey("companies.id"), nullable=False)

    company = relationship("Company", back_populates="departments")

    __table_args__ = (
        UniqueConstraint('dept_name', 'company_id', name='uq_dept_company'),
    )