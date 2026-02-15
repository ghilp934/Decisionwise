"""Pytest configuration and fixtures for worker tests."""

import os
import sys
from pathlib import Path

import pytest
import redis
from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker
from sqlalchemy.pool import StaticPool

# Add API path for imports
sys.path.insert(0, str(Path(__file__).parent.parent.parent / "api"))

from dpp_api.budget import BudgetManager
from dpp_api.db.models import Base

# Use PostgreSQL for tests (BIGINT autoincrement requires PostgreSQL)
TEST_DATABASE_URL = os.getenv("DATABASE_URL") or "postgresql://dpp_user:dpp_pass@localhost:5432/dpp"

# Redis test settings
REDIS_TEST_HOST = "localhost"
REDIS_TEST_PORT = 6379
REDIS_TEST_DB = 15  # Use separate DB for tests


@pytest.fixture(scope="function")
def db_session() -> Session:
    """
    Create a fresh database session for each test.

    Uses PostgreSQL if DATABASE_URL is set, otherwise in-memory SQLite.
    """
    # Create engine
    if "postgresql" in TEST_DATABASE_URL:
        # PostgreSQL: use normal connection
        engine = create_engine(TEST_DATABASE_URL)
    else:
        # SQLite: use in-memory with special settings
        engine = create_engine(
            TEST_DATABASE_URL,
            connect_args={"check_same_thread": False},
            poolclass=StaticPool,
        )

    # Create all tables (idempotent for PostgreSQL)
    Base.metadata.create_all(engine)

    # Create session
    SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
    session = SessionLocal()

    try:
        yield session
        # Rollback any uncommitted changes
        session.rollback()
    finally:
        # Cleanup test data for PostgreSQL (to avoid cross-test contamination)
        if "postgresql" in TEST_DATABASE_URL:
            from dpp_api.db.models import Run, TenantPlan, TenantUsageDaily

            # Delete test data (patterns: tenant_t2_*, tenant_t3_*, etc.)
            session.query(TenantUsageDaily).filter(
                TenantUsageDaily.tenant_id.like("tenant_t%")
            ).delete(synchronize_session=False)
            session.query(TenantPlan).filter(
                TenantPlan.tenant_id.like("tenant_t%")
            ).delete(synchronize_session=False)
            session.query(Run).filter(
                Run.tenant_id.like("tenant_t%")
            ).delete(synchronize_session=False)
            session.commit()

        session.close()
        # Only drop tables for SQLite (PostgreSQL tables persist)
        if "sqlite" in TEST_DATABASE_URL:
            Base.metadata.drop_all(engine)


@pytest.fixture(scope="function")
def redis_client() -> redis.Redis:
    """Create a fresh Redis client for each test.

    Uses Redis DB 15 for tests and flushes it before each test.
    RC-4: Force production RedisClient singleton to use TEST DB.
    """
    from dpp_api.db.redis_client import RedisClient

    # RC-4 Safety: Reset singleton before test
    RedisClient.reset()

    # Create test client with explicit test DB
    client = redis.Redis(
        host=REDIS_TEST_HOST,
        port=REDIS_TEST_PORT,
        db=REDIS_TEST_DB,
        decode_responses=True,
    )

    # Flush test database before each test
    client.flushdb()

    # RC-4: Override singleton so production code uses test client
    RedisClient._instance = client

    try:
        yield client
    finally:
        # Clean up after test
        client.flushdb()
        # Reset singleton to clean state
        RedisClient.reset()


@pytest.fixture(scope="function")
def budget_manager(redis_client: redis.Redis, db_session: Session) -> BudgetManager:
    """Create BudgetManager instance for tests."""
    return BudgetManager(redis_client, db_session)
