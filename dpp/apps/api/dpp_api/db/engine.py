"""Database engine builder (SSOT).

Spec Lock: Supabase pooler + NullPool policy + Production guardrails.
- Default: NullPool (client-side pooling disabled)
- Supabase PROD: sslmode=verify-full enforced + CA bundle required (DPP_DB_SSLROOTCERT)
- Supabase non-PROD: sslmode=require (default when DPP_DB_SSLMODE unset)
- PROD: Pooler Transaction mode (port 6543) enforced
- PROD: ACK variables required for deployment safety
- ENV: DPP_DB_POOL=nullpool|queuepool (default: nullpool)
- ENV: DPP_DB_SSLMODE=require|verify-ca|verify-full (PROD+Supabase default: "verify-full")
- ENV: DPP_DB_SSLROOTCERT=<path> (required for verify-ca/verify-full)

SSL Policy (Spec Lock) — delegated to dpp_api.db.ssl_policy:
  DPP_DB_SSLMODE set   → ENV is authoritative (SSOT).
                           URL sslmode conflict + PROD → RuntimeError.
                           URL sslmode conflict + DEV  → WARNING log.
  DPP_DB_SSLMODE unset → URL sslmode (if present) used (legacy compat).
                           Neither set → verify-full (PROD+Supabase) or require (else).
  PROD + Supabase host → sslmode MUST be verify-full; sslrootcert MUST be readable.
"""

import os
import re
from typing import Any
from urllib.parse import urlparse

from sqlalchemy import Engine, NullPool, QueuePool, create_engine
from sqlalchemy.orm import Session, sessionmaker

from dpp_api.db.ssl_policy import (
    effective_sslmode,
    get_sslrootcert,
    resolve_ssl_settings,
    validate_ssl_settings,
)
from dpp_api.db.url_policy import is_supabase_host


def _is_supabase_host(url: str) -> bool:
    """Check if URL points to Supabase host. Delegates to url_policy.is_supabase_host."""
    return is_supabase_host(url)


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

    # P0-1: SSL Mode enforcement (PROD + Supabase requires verify-full).
    # Spec Lock: effective_sslmode() applies ENV-SSOT precedence (DPP_DB_SSLMODE over URL).
    #   May raise RuntimeError if ENV and URL conflict in PROD.
    eff_mode = effective_sslmode(url, dp_env)
    if eff_mode != "verify-full":
        raise RuntimeError(
            f"PRODUCTION GUARDRAIL: Supabase DB connection requires sslmode=verify-full "
            f"in production, got '{eff_mode}'. "
            "Set DPP_DB_SSLMODE=verify-full in environment and mount the Supabase CA "
            "ConfigMap (DPP_DB_SSLROOTCERT=/etc/ssl/certs/supabase-ca/supabase-ca.crt). "
            "See ops/runbooks/db_ssl_verify_full.md for setup instructions."
        )
    # Also confirm CA bundle is present and readable for verify-full.
    validate_ssl_settings(eff_mode, get_sslrootcert())

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

    # Supabase SSL enforcement via connect_args (SSOT: ssl_policy.resolve_ssl_settings).
    # Handles sslmode + sslrootcert from ENV, applies PROD defaults (verify-full),
    # and fails fast if the CA bundle is missing for CA-required modes.
    # Non-Supabase hosts return {} (no enforcement from this layer).
    connect_args: dict[str, Any] = {}
    if _is_supabase_host(url):
        connect_args = resolve_ssl_settings(url, dp_env)

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
