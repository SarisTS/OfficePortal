from sqlalchemy import Column, Integer, DateTime, Boolean, func, ForeignKey


class AuditMixin:
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False)

    deleted_at = Column(DateTime(timezone=True), nullable=True)

    created_by = Column(Integer)
    updated_by = Column(Integer)

    is_deleted = Column(Boolean, default=False, nullable=False)
    is_active  = Column(Boolean, default=True, nullable=False)
