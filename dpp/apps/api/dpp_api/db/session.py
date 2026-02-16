"""Database session management.

Spec Lock: Uses unified engine builder (SSOT) with NullPool default.
"""

from typing import Generator

from sqlalchemy.orm import Session

from dpp_api.db.engine import build_engine, build_sessionmaker

# Create engine using SSOT builder (default: NullPool)
engine = build_engine()

# Create session factory
SessionLocal = build_sessionmaker(engine)


def get_db() -> Generator[Session, None, None]:
    """
    Get database session.

    Yields:
        Session: SQLAlchemy session
    """
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
