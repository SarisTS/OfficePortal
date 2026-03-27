from sqlalchemy import Column, Integer, String, ForeignKey, UniqueConstraint
from sqlalchemy.orm import relationship
from app.database.base import Base
from app.models.base import AuditMixin


class Hostel(Base, AuditMixin):
    __tablename__ = "hostels"

    id = Column(Integer, primary_key=True)

    name = Column(String(255), nullable=False, index=True)
    flat_no = Column(String(50), index=True)

    address_line_1 = Column(String(255))
    address_line_2 = Column(String(255))
    landmark = Column(String(255))

    location_id = Column(Integer, ForeignKey("locations.id"), nullable=False, index=True)
    location = relationship("Location")
    employees = relationship("Employee", back_populates="hostel")

    __table_args__ = (
        UniqueConstraint("name", "location_id", name="uq_hostel_name_location"),
    )