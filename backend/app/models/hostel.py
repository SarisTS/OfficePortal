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

    # Nullable so existing rows (created before per-company scoping was
    # introduced) remain valid. New rows are stamped with the creator's
    # company_id for office_admin or accept it from the payload for
    # super_admin. NULL = legacy / global hostel — readable by any admin,
    # modifiable only by super_admin until they classify it.
    company_id = Column(Integer, ForeignKey("companies.id"), nullable=True, index=True)
    company = relationship("Company")

    employees = relationship("Employee", back_populates="hostel")

    __table_args__ = (
        UniqueConstraint("name", "location_id", name="uq_hostel_name_location"),
    )
