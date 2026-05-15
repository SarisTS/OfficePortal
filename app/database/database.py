from contextlib import contextmanager

from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker

from app.core.config import settings

DATABASE_URL = settings.DATABASE_URL

# Pool tuning notes:
#  - pool_size=10        : steady-state connections kept open per process.
#  - max_overflow=10     : temporary connections beyond pool_size during bursts;
#                          closed after pool_timeout. Total cap = 20 per process.
#  - pool_timeout=30     : seconds to wait for a connection before giving up.
#                          Better to fail fast than queue requests indefinitely.
#  - pool_recycle=1800   : recycle every 30 min to dodge stale connections
#                          killed by Postgres / firewall idle timeouts.
#  - pool_pre_ping=True  : cheap SELECT 1 before checkout — catches a connection
#                          that died since we last used it.
engine = create_engine(
    DATABASE_URL,
    pool_size=10,
    max_overflow=10,
    pool_timeout=30,
    pool_recycle=1800,
    pool_pre_ping=True,
)

SessionLocal = sessionmaker(
    autocommit=False,
    autoflush=False,
    bind=engine,
)


def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


@contextmanager
def with_transaction(db: Session):
    """Commit on success, rollback on any exception.

    Usage:

        with with_transaction(db):
            db.add(thing)
            db.flush()           # raises here → rollback + re-raise
            other_thing.field = "x"

    The wrapped block must NOT call ``db.commit()`` itself — leave that to
    the helper so multi-statement units stay atomic. HTTPException raised
    inside the block is treated the same as any other: rollback, re-raise,
    let FastAPI turn it into a response.
    """
    try:
        yield db
        db.commit()
    except Exception:
        db.rollback()
        raise