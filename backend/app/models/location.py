from sqlalchemy import Column, Integer, String, Index
from app.database.base import Base
from app.models.base import AuditMixin


class Location(Base, AuditMixin):
    __tablename__ = "locations"

    id          = Column(Integer, primary_key=True, index=True)
    # Geo reference data lives in location.json (no countries/states/cities
    # tables exist), so FK constraints can't be added. Indexes still help the
    # lookups in app/crud/location.py.
    country_id  = Column(Integer, nullable=False)
    state_id    = Column(Integer, nullable=False)
    city_id     = Column(Integer, nullable=False)
    postal_code = Column(String(20), nullable=True)

    __table_args__ = (
        Index("idx_locations_country", "country_id"),
        Index("idx_locations_state", "state_id"),
        Index("idx_locations_city", "city_id"),
    )
