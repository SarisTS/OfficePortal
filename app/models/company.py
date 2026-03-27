from sqlalchemy import Column, Integer, String, ForeignKey, DateTime
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func
from app.database.base import Base
from app.models.base import AuditMixin


class Company(Base, AuditMixin):
    __tablename__ = "companies"

    id = Column(Integer, primary_key=True, index=True)

    name = Column(String(255), nullable=False)
    email = Column(String(255), nullable=True)
    phone = Column(String(20), nullable=True)

    flat_no = Column(String(50), nullable=True)
    address_line_1 = Column(String(255), nullable=True)
    address_line_2 = Column(String(255), nullable=True)
    landmark = Column(String(255), nullable=True)

    location_id = Column(Integer, ForeignKey("locations.id"), nullable=True)

    parent_company_id = Column(Integer, ForeignKey("companies.id"))
    
    location = relationship("Location")
    # ✅ Geo-fencing locations
    locations = relationship("CompanyLocation", back_populates="company")
    parent_company = relationship("Company", remote_side=[id])
    employees = relationship("Employee", back_populates="company")
    departments = relationship("Department", back_populates="company")
