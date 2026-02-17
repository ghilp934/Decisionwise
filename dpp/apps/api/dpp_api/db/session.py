"""Database session management.

Spec Lock: Uses unified engine builder (SSOT) with NullPool default.
"""

import os
from typing import Generator

from sqlalchemy.orm import Session

from dpp_api.db.engine import build_engine, build_sessionmaker

# ENV-01: Database URL from environment
# Production fail-fast: DATABASE_URL is mandatory in prod/production
DP_ENV = os.getenv("DP_ENV", "").lower()
DATABASE_URL = os.getenv("DATABASE_URL")

if DP_ENV in {"prod", "production"}:
    # Production: DATABASE_URL is required (fail-fast)
    if not DATABASE_URL:
        raise RuntimeError(
            "DATABASE_URL environment variable is required in production (DP_ENV=prod/production). "
            "Check deployment configuration and secrets injection."
        )
else:
    # Development/CI: fallback to docker-compose default
    if not DATABASE_URL:
        DATABASE_URL = "postgresql://dpp_user:dpp_pass@localhost:5432/dpp"

# Create engine using SSOT builder (default: NullPool)
engine = build_engine(DATABASE_URL)

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
