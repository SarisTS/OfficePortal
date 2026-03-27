from sqlalchemy import Column, Integer, String
from app.database.base import Base
from app.models.base import AuditMixin

class Location(Base, AuditMixin):
    __tablename__ = "locations"

    id               = Column(Integer, primary_key=True, index=True)
    country_id       = Column(Integer,  nullable=False)
    state_id         = Column(Integer,  nullable=False)
    city_id          = Column(Integer,  nullable=False)
    postal_code      = Column(String(20), nullable=True)

   
