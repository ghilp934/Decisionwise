#!/usr/bin/env python3
"""
Supabase Production Preflight Validator.

배포/운영자가 Supabase 대시보드 수동 설정 완료 여부를 배포 직전에 확인하는 도구.

Usage:
    python scripts/supabase_preflight.py
    python scripts/supabase_preflight.py --relaxed

Exit Codes:
    0: PASS (all checks passed)
    1: FAIL (validation failed)

Environment Variables:
    DATABASE_URL: Production database connection string (required)
    DP_ENV: Environment name (must be "prod" or "production")
    DPP_ACK_SUPABASE_NETWORK_RESTRICTIONS: "1" confirms Network Restrictions configured
    DPP_ACK_SUPABASE_BACKUP_POLICY: "1" confirms Backup policy configured
    DPP_ACK_BYPASS: "1" bypasses ACK checks (NOT recommended for production)

Relaxed Mode (--relaxed):
    Skip ACK checks, only validate DATABASE_URL structure (port 6543, pooler, sslmode).
"""

import argparse
import os
import sys
from urllib.parse import urlparse


def _is_supabase_host(url: str) -> bool:
    """Check if URL points to Supabase host."""
    return ".supabase.co" in url or ".pooler.supabase.com" in url


def validate_database_url(url: str) -> tuple[bool, list[str]]:
    """
    Validate DATABASE_URL structure for Supabase production.

    Returns:
        (is_valid, error_messages)
    """
    errors = []

    if not _is_supabase_host(url):
        # Not Supabase, skip validation
        return True, []

    # P0-1: SSL Mode enforcement
    if "sslmode=require" not in url:
        errors.append(
            "ERROR: DATABASE_URL missing 'sslmode=require'. "
            "Fix: Add '?sslmode=require' to connection string."
        )

    # Parse URL
    try:
        parsed = urlparse(url)
    except Exception as e:
        errors.append(f"ERROR: Invalid DATABASE_URL format: {e}")
        return False, errors

    # P0-1: Port 6543 enforcement
    port = parsed.port
    if port is None:
        errors.append(
            "ERROR: DATABASE_URL missing explicit port. "
            "Fix: Use Pooler Transaction mode (port 6543)."
        )
    elif port != 6543:
        errors.append(
            f"ERROR: Supabase port must be 6543 (Pooler Transaction mode), got {port}. "
            "Fix: Update to Pooler Transaction connection string from Supabase Dashboard."
        )

    # P0-1: Pooler host enforcement
    hostname = parsed.hostname or ""
    if "pooler" not in hostname.lower():
        errors.append(
            f"ERROR: Supabase hostname must include 'pooler', got {hostname}. "
            "Fix: Use Pooler Transaction mode connection string from Supabase Dashboard."
        )

    return len(errors) == 0, errors


def validate_ack_variables(relaxed: bool = False) -> tuple[bool, list[str]]:
    """
    Validate ACK environment variables.

    Args:
        relaxed: If True, skip ACK checks.

    Returns:
        (is_valid, error_messages)
    """
    if relaxed:
        return True, []

    errors = []

    # ACK bypass check
    if os.getenv("DPP_ACK_BYPASS") == "1":
        print("WARNING: DPP_ACK_BYPASS=1 detected. ACK checks bypassed.")
        return True, []

    # P0-2: Network Restrictions ACK
    if os.getenv("DPP_ACK_SUPABASE_NETWORK_RESTRICTIONS") != "1":
        errors.append(
            "ERROR: DPP_ACK_SUPABASE_NETWORK_RESTRICTIONS=1 required. "
            "Fix: Complete ops/runbooks/supabase_hardening.md checklist."
        )

    # P0-4: Backup Policy ACK
    if os.getenv("DPP_ACK_SUPABASE_BACKUP_POLICY") != "1":
        errors.append(
            "ERROR: DPP_ACK_SUPABASE_BACKUP_POLICY=1 required. "
            "Fix: Complete ops/runbooks/db_backup_restore.md checklist."
        )

    return len(errors) == 0, errors


def validate_api_keys() -> tuple[bool, list[str]]:
    """
    Validate that Supabase API keys are not present in environment.

    Returns:
        (is_valid, error_messages)
    """
    errors = []

    if os.getenv("SUPABASE_SERVICE_ROLE_KEY"):
        errors.append(
            "ERROR: SUPABASE_SERVICE_ROLE_KEY detected in environment. "
            "Fix: Remove from deployment config (server-side Postgres only)."
        )

    if os.getenv("SUPABASE_ANON_KEY"):
        errors.append(
            "ERROR: SUPABASE_ANON_KEY detected in environment. "
            "Fix: Remove from deployment config (server-side Postgres only)."
        )

    return len(errors) == 0, errors


def main():
    parser = argparse.ArgumentParser(
        description="Supabase Production Preflight Validator",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  python scripts/supabase_preflight.py
  python scripts/supabase_preflight.py --relaxed
        """,
    )
    parser.add_argument(
        "--relaxed",
        action="store_true",
        help="Skip ACK checks, only validate DATABASE_URL structure",
    )
    args = parser.parse_args()

    # Check DP_ENV
    dp_env = os.getenv("DP_ENV", "").lower()
    if dp_env not in {"prod", "production"}:
        print(f"INFO: DP_ENV={dp_env or '(not set)'} - Skipping production preflight.")
        print("PASS: Non-production environment")
        sys.exit(0)

    # Get DATABASE_URL
    database_url = os.getenv("DATABASE_URL")
    if not database_url:
        print("ERROR: DATABASE_URL not set in environment.")
        print("FAIL: Missing DATABASE_URL")
        sys.exit(1)

    # Skip validation if not Supabase
    if not _is_supabase_host(database_url):
        print("INFO: Non-Supabase database detected - Skipping Supabase-specific checks.")
        print("PASS: Non-Supabase database")
        sys.exit(0)

    # Run validations
    all_errors = []

    # 1. Validate DATABASE_URL structure
    url_valid, url_errors = validate_database_url(database_url)
    all_errors.extend(url_errors)

    # 2. Validate ACK variables
    ack_valid, ack_errors = validate_ack_variables(relaxed=args.relaxed)
    all_errors.extend(ack_errors)

    # 3. Validate API keys
    keys_valid, keys_errors = validate_api_keys()
    all_errors.extend(keys_errors)

    # Print results
    if all_errors:
        print("FAIL: Supabase production preflight validation failed")
        print()
        for error in all_errors:
            print(error)
        sys.exit(1)
    else:
        mode = "relaxed" if args.relaxed else "strict"
        print(f"PASS: Supabase production preflight validation successful ({mode} mode)")
        sys.exit(0)


if __name__ == "__main__":
    main()
