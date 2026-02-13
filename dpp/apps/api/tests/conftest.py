"""Pytest configuration and fixtures."""

import os

import pytest
import redis
from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker
from sqlalchemy.pool import StaticPool

from dpp_api.db.models import Base

# Use PostgreSQL for monetization tests (BIGINT autoincrement requires PostgreSQL)
# Set to "sqlite:///:memory:" for fast unit tests
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
            from dpp_api.db.models import TenantPlan, TenantUsageDaily

            # Delete test tenant's data (tenant will be recreated by fixtures)
            session.query(TenantUsageDaily).filter(
                TenantUsageDaily.tenant_id.like("tenant_%_test%")
            ).delete(synchronize_session=False)
            session.query(TenantPlan).filter(
                TenantPlan.tenant_id.like("tenant_%_test%")
            ).delete(synchronize_session=False)
            session.commit()

        session.close()
        # Only drop tables for SQLite (PostgreSQL tables persist)
        if "sqlite" in TEST_DATABASE_URL:
            Base.metadata.drop_all(engine)


@pytest.fixture(scope="function")
def redis_client() -> redis.Redis:
    """
    Create a fresh Redis client for each test.

    Uses Redis DB 15 for tests and flushes it before each test.
    """
    client = redis.Redis(
        host=REDIS_TEST_HOST,
        port=REDIS_TEST_PORT,
        db=REDIS_TEST_DB,
        decode_responses=True,
    )

    # Flush test database before each test
    client.flushdb()

    try:
        yield client
    finally:
        # Clean up after test
        client.flushdb()
        client.close()
