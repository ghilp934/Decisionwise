"""Database engine builder (SSOT).

Spec Lock: Supabase pooler + NullPool policy.
- Default: NullPool (client-side pooling disabled)
- Supabase hosts: sslmode=require enforced
- ENV: DPP_DB_POOL=nullpool|queuepool (default: nullpool)
"""

import os
import re
from typing import Any

from sqlalchemy import Engine, NullPool, QueuePool, create_engine
from sqlalchemy.orm import Session, sessionmaker


def _is_supabase_host(url: str) -> bool:
    """Check if URL points to Supabase host (.supabase.co or .pooler.supabase.com)."""
    return ".supabase.co" in url or ".pooler.supabase.com" in url


def _mask_password(url: str) -> str:
    """Mask password in database URL for safe logging."""
    return re.sub(r"://([^:]+):([^@]+)@", r"://\1:***@", url)


def build_engine(database_url: str | None = None) -> Engine:
    """
    Build SQLAlchemy engine with Supabase SSOT policy.

    Spec Lock (Hard Locks):
    1. Default pool: NullPool (poolclass=NullPool)
    2. pool_pre_ping=True (always verify connections)
    3. Supabase host → sslmode=require enforced (connect_args)
    4. No QueuePool params (pool_size/max_overflow) when using NullPool

    Args:
        database_url: Database URL. If None, reads from env DATABASE_URL.

    Returns:
        SQLAlchemy Engine instance.

    Raises:
        ValueError: If DATABASE_URL not provided and not in environment.

    Environment Variables:
        DATABASE_URL: Runtime connection string (required if not passed as arg)
        DPP_DB_POOL: Pool mode - "nullpool" (default) | "queuepool"
        DPP_DB_POOL_SIZE: QueuePool size (default: 5, only for queuepool)
        DPP_DB_MAX_OVERFLOW: QueuePool overflow (default: 10, only for queuepool)

    Examples:
        >>> # Default NullPool
        >>> engine = build_engine()
        >>> # QueuePool (internal dev only)
        >>> os.environ["DPP_DB_POOL"] = "queuepool"
        >>> engine = build_engine()
    """
    # Determine URL
    url = database_url or os.getenv("DATABASE_URL")
    if not url:
        raise ValueError(
            "DATABASE_URL is required. "
            "Pass as argument or set DATABASE_URL environment variable."
        )

    # Supabase SSL enforcement
    connect_args: dict[str, Any] = {}
    if _is_supabase_host(url):
        # Only add sslmode if not already in URL
        if "sslmode=" not in url:
            connect_args["sslmode"] = "require"

    # Pool mode selection
    pool_mode = os.getenv("DPP_DB_POOL", "nullpool").lower()

    if pool_mode == "nullpool":
        # Spec Lock: NullPool (default, recommended for Supabase pooler transaction mode)
        engine = create_engine(
            url,
            poolclass=NullPool,
            pool_pre_ping=True,
            connect_args=connect_args,
        )
    elif pool_mode == "queuepool":
        # QueuePool (internal dev/special cases only)
        pool_size = int(os.getenv("DPP_DB_POOL_SIZE", "5"))
        max_overflow = int(os.getenv("DPP_DB_MAX_OVERFLOW", "10"))
        engine = create_engine(
            url,
            pool_pre_ping=True,
            pool_size=pool_size,
            max_overflow=max_overflow,
            connect_args=connect_args,
        )
    else:
        raise ValueError(
            f"Invalid DPP_DB_POOL value: {pool_mode}. "
            "Must be 'nullpool' or 'queuepool'."
        )

    # Safe logging (mask password)
    pool_class_name = engine.pool.__class__.__name__
    # DO NOT log full URL with password
    # Only log masked version for diagnostics
    if os.getenv("LOG_LEVEL") == "DEBUG":
        import logging

        logger = logging.getLogger(__name__)
        logger.debug(
            "Database engine created: pool=%s, url=%s",
            pool_class_name,
            _mask_password(url),
        )

    return engine


def build_sessionmaker(engine: Engine) -> sessionmaker[Session]:
    """
    Build SQLAlchemy sessionmaker.

    Args:
        engine: SQLAlchemy Engine instance.

    Returns:
        sessionmaker instance configured with autocommit=False, autoflush=False.

    Examples:
        >>> engine = build_engine()
        >>> SessionLocal = build_sessionmaker(engine)
        >>> with SessionLocal() as session:
        ...     # use session
    """
    return sessionmaker(autocommit=False, autoflush=False, bind=engine)
