"""Database engine builder (SSOT).

Spec Lock: Supabase pooler + NullPool policy + Production guardrails.
- Default: NullPool (client-side pooling disabled)
- Supabase hosts: sslmode=require enforced
- PROD: Pooler Transaction mode (port 6543) enforced
- PROD: ACK variables required for deployment safety
- ENV: DPP_DB_POOL=nullpool|queuepool (default: nullpool)
"""

import os
import re
from typing import Any
from urllib.parse import urlparse

from sqlalchemy import Engine, NullPool, QueuePool, create_engine
from sqlalchemy.orm import Session, sessionmaker


def _is_supabase_host(url: str) -> bool:
    """Check if URL points to Supabase host (.supabase.co or .pooler.supabase.com)."""
    return ".supabase.co" in url or ".pooler.supabase.com" in url


def _mask_password(url: str) -> str:
    """Mask password in database URL for safe logging."""
    return re.sub(r"://([^:]+):([^@]+)@", r"://\1:***@", url)


def _validate_supabase_production_config(url: str, dp_env: str) -> None:
    """
    Validate Supabase production configuration (P0 guardrails).

    Raises:
        RuntimeError: If production requirements not met.

    Environment toggles (emergency/testing only):
        DPP_SUPABASE_ALLOW_NON_6543: "1" to allow non-6543 ports
        DPP_SUPABASE_ALLOW_DIRECT: "1" to allow direct connections (non-pooler)
        DPP_ALLOW_SUPABASE_API_KEYS: "1" to allow SUPABASE_SERVICE_ROLE_KEY/ANON_KEY
        DPP_ACK_BYPASS: "1" to bypass ACK checks (NEVER use in production)
        DPP_ACK_SUPABASE_NETWORK_RESTRICTIONS: "1" confirms Network Restrictions configured
        DPP_ACK_SUPABASE_BACKUP_POLICY: "1" confirms Backup policy configured
    """
    if dp_env not in {"prod", "production"}:
        return  # Guardrails only apply to production

    if not _is_supabase_host(url):
        return  # Not Supabase, skip validation

    # Parse URL
    parsed = urlparse(url)

    # P0-1: SSL Mode enforcement
    if "sslmode=require" not in url:
        raise RuntimeError(
            "PRODUCTION GUARDRAIL: Supabase connections MUST use sslmode=require. "
            "Add '?sslmode=require' to DATABASE_URL or include in connect_args."
        )

    # P0-1: Port 6543 enforcement (Pooler Transaction mode)
    port = parsed.port
    if port is None:
        raise RuntimeError(
            "PRODUCTION GUARDRAIL: DATABASE_URL must explicitly specify port. "
            "For Supabase production, use Pooler Transaction mode (port 6543). "
            "Example: postgres://...@host.pooler.supabase.com:6543/postgres?sslmode=require"
        )

    if port != 6543:
        if os.getenv("DPP_SUPABASE_ALLOW_NON_6543") == "1":
            import logging
            logger = logging.getLogger(__name__)
            logger.warning(
                "PRODUCTION WARNING: Using non-6543 port (%d) with DPP_SUPABASE_ALLOW_NON_6543=1. "
                "Recommended: Pooler Transaction mode port 6543.",
                port,
            )
        else:
            raise RuntimeError(
                f"PRODUCTION GUARDRAIL: Supabase port must be 6543 (Pooler Transaction mode), got {port}. "
                "Direct connections (port 5432) are not recommended for production runtime. "
                "Fix: Use Pooler Transaction mode connection string from Supabase Dashboard. "
                "Emergency override: DPP_SUPABASE_ALLOW_NON_6543=1 (not recommended)."
            )

    # P0-1: Pooler host enforcement
    hostname = parsed.hostname or ""
    if "pooler" not in hostname.lower():
        if os.getenv("DPP_SUPABASE_ALLOW_DIRECT") == "1":
            import logging
            logger = logging.getLogger(__name__)
            logger.warning(
                "PRODUCTION WARNING: Using direct connection (non-pooler) with DPP_SUPABASE_ALLOW_DIRECT=1. "
                "Recommended: Pooler Transaction mode for production runtime."
            )
        else:
            raise RuntimeError(
                f"PRODUCTION GUARDRAIL: Supabase hostname must include 'pooler' (Pooler mode), got {hostname}. "
                "Direct connections are not recommended for production runtime. "
                "Fix: Use Pooler Transaction mode connection string from Supabase Dashboard. "
                "Emergency override: DPP_SUPABASE_ALLOW_DIRECT=1 (not recommended)."
            )

    # P0-3: API Keys hygiene
    if os.getenv("SUPABASE_SERVICE_ROLE_KEY") or os.getenv("SUPABASE_ANON_KEY"):
        if os.getenv("DPP_ALLOW_SUPABASE_API_KEYS") != "1":
            raise RuntimeError(
                "PRODUCTION GUARDRAIL: SUPABASE_SERVICE_ROLE_KEY or SUPABASE_ANON_KEY detected in environment. "
                "This project uses direct Postgres connections only (server-side). "
                "Supabase API keys should NOT be present in runtime environment. "
                "Fix: Remove SUPABASE_SERVICE_ROLE_KEY and SUPABASE_ANON_KEY from deployment config. "
                "Emergency override: DPP_ALLOW_SUPABASE_API_KEYS=1 (not recommended)."
            )

    # P0-2, P0-4: ACK checks (manual configuration verification)
    if os.getenv("DPP_ACK_BYPASS") == "1":
        import logging
        logger = logging.getLogger(__name__)
        logger.warning(
            "PRODUCTION WARNING: ACK checks bypassed with DPP_ACK_BYPASS=1. "
            "This should NEVER be used in production deployments."
        )
        return

    # P0-2: Network Restrictions ACK
    if os.getenv("DPP_ACK_SUPABASE_NETWORK_RESTRICTIONS") != "1":
        raise RuntimeError(
            "PRODUCTION GUARDRAIL: DPP_ACK_SUPABASE_NETWORK_RESTRICTIONS=1 required. "
            "This confirms Supabase Network Restrictions (IP allowlist) configured in dashboard. "
            "Fix: Complete ops/runbooks/supabase_hardening.md checklist, then set ACK variable. "
            "See: ops/runbooks/supabase_hardening.md for configuration steps."
        )

    # P0-4: Backup Policy ACK
    if os.getenv("DPP_ACK_SUPABASE_BACKUP_POLICY") != "1":
        raise RuntimeError(
            "PRODUCTION GUARDRAIL: DPP_ACK_SUPABASE_BACKUP_POLICY=1 required. "
            "This confirms backup/restore procedures tested and scheduled. "
            "Fix: Complete ops/runbooks/db_backup_restore.md checklist, then set ACK variable. "
            "See: ops/runbooks/db_backup_restore.md for backup procedures."
        )


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

    # Production guardrails (P0-1, P0-2, P0-3, P0-4)
    dp_env = os.getenv("DP_ENV", "").lower()
    _validate_supabase_production_config(url, dp_env)

    # Supabase SSL enforcement
    connect_args: dict[str, Any] = {}
    if _is_supabase_host(url):
        # Only add sslmode if not already in URL
        if "sslmode=" not in url:
            connect_args["sslmode"] = "require"

    # Application name (P0-1: connection tagging for observability)
    app_name = os.getenv("DPP_DB_APPLICATION_NAME", "decisionproof-api")
    if app_name:
        connect_args["application_name"] = app_name

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
