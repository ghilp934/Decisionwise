#!/usr/bin/env python3
"""Database smoke check - STRICT drift detection with index dup toggle + RLS verification.

Verifies runtime DB schema matches repository baseline (models.py + alembic migrations).

Exit codes:
    0: PASS
    1: FAIL (drift detected)
    2: ERROR (env/tooling/connection failure)

Environment variables:
    DATABASE_URL: Required. PostgreSQL connection string.
    DATABASE_SCHEMA: Optional. Default "public".
    DEBUG: Optional. Set to "1" for stderr debug output.
    RELAXED: Optional. Set to "1" to allow index duplicates (overrides STRICT).
    STRICT: Optional. Default "1". Enforced unless RELAXED=1.
    JSON_OUTPUT: Optional. Set to "1" to output JSON format (default: text).
    SAVE_EVIDENCE: Optional. Set to "1" to save JSON report to evidence/ directory.
    ALLOW_EXTRA_COLUMNS: Optional. Set to "1" to allow extra columns not in spec.

Mode:
    - STRICT (default): Each index signature must have exactly 1 index with canonical name.
                        Extra signatures = DRIFT. Index duplicates = DRIFT.
    - RELAXED (RELAXED=1): Each index signature must have >=1 index with canonical or alias name.
                           Extra signatures = WARN only. Index duplicates = allowed.
"""

import json
import os
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

# --- ENGINE POLICY (Spec Lock) ---
try:
    from dpp_api.db.engine import build_engine
    USE_SSOT_ENGINE = True
except ImportError:
    from sqlalchemy import create_engine
    from sqlalchemy.pool import NullPool
    USE_SSOT_ENGINE = False

from sqlalchemy import text
from sqlalchemy.engine import Engine
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.inspection import inspect


# --- EXPECTED SCHEMA (SOURCE OF TRUTH: models.py + alembic migrations) ---

# Table specs: {table_name: [(col_name, udt_name, is_nullable), ...]}
# Order matches ordinal_position in information_schema.columns
EXPECTED_TABLE_SPECS = {
    "tenants": [
        ("tenant_id", "text", "NO"),
        ("display_name", "text", "NO"),
        ("status", "text", "NO"),
        ("created_at", "timestamptz", "NO"),
    ],
    "api_keys": [
        ("key_id", "uuid", "NO"),
        ("tenant_id", "text", "NO"),
        ("key_hash", "text", "NO"),
        ("label", "text", "YES"),
        ("status", "text", "NO"),
        ("created_at", "timestamptz", "NO"),
        ("last_used_at", "timestamptz", "YES"),
    ],
    "runs": [
        ("run_id", "uuid", "NO"),
        ("tenant_id", "text", "NO"),
        ("pack_type", "text", "NO"),
        ("profile_version", "text", "NO"),
        ("status", "text", "NO"),
        ("money_state", "text", "NO"),
        ("idempotency_key", "text", "YES"),
        ("payload_hash", "text", "NO"),
        ("version", "int8", "NO"),
        ("reservation_max_cost_usd_micros", "int8", "NO"),
        ("actual_cost_usd_micros", "int8", "YES"),
        ("minimum_fee_usd_micros", "int8", "NO"),
        ("result_bucket", "text", "YES"),
        ("result_key", "text", "YES"),
        ("result_sha256", "text", "YES"),
        ("retention_until", "timestamptz", "NO"),
        ("lease_token", "text", "YES"),
        ("lease_expires_at", "timestamptz", "YES"),
        ("finalize_token", "text", "YES"),
        ("finalize_stage", "text", "YES"),
        ("finalize_claimed_at", "timestamptz", "YES"),
        ("last_error_reason_code", "text", "YES"),
        ("last_error_detail", "text", "YES"),
        ("trace_id", "text", "YES"),
        ("created_at", "timestamptz", "NO"),
        ("updated_at", "timestamptz", "NO"),
        ("completed_at", "timestamptz", "YES"),
        ("timebox_sec", "int8", "YES"),
        ("min_reliability_score", "float8", "YES"),
        ("inputs_json", "json", "YES"),
    ],
    "plans": [
        ("plan_id", "text", "NO"),
        ("name", "text", "NO"),
        ("status", "text", "NO"),
        ("default_profile_version", "text", "NO"),
        ("features_json", "json", "NO"),
        ("limits_json", "json", "NO"),
        ("created_at", "timestamptz", "NO"),
        ("updated_at", "timestamptz", "NO"),
    ],
    "tenant_plans": [
        ("id", "int8", "NO"),
        ("tenant_id", "text", "NO"),
        ("plan_id", "text", "NO"),
        ("status", "text", "NO"),
        ("effective_from", "timestamptz", "NO"),
        ("effective_to", "timestamptz", "YES"),
        ("changed_by", "text", "YES"),
        ("change_reason", "text", "YES"),
        ("created_at", "timestamptz", "NO"),
    ],
    "tenant_usage_daily": [
        ("id", "int8", "NO"),
        ("tenant_id", "text", "NO"),
        ("usage_date", "date", "NO"),
        ("runs_count", "int8", "NO"),
        ("success_count", "int8", "NO"),
        ("fail_count", "int8", "NO"),
        ("cost_usd_micros_sum", "int8", "NO"),
        ("reserved_usd_micros_sum", "int8", "NO"),
        ("created_at", "timestamptz", "NO"),
        ("updated_at", "timestamptz", "NO"),
    ],
}

# Primary keys: {table_name: [col_names]}
EXPECTED_PK = {
    "tenants": ["tenant_id"],
    "api_keys": ["key_id"],
    "runs": ["run_id"],
    "plans": ["plan_id"],
    "tenant_plans": ["id"],
    "tenant_usage_daily": ["id"],
}

# Unique constraints: {table_name: [(constraint_name, [col_names])]}
EXPECTED_UNIQUE_CONSTRAINTS = {
    "runs": [("uq_runs_tenant_idempotency", ["tenant_id", "idempotency_key"])],
}

# Index groups: {table_name: [group, ...]}
# group = {"signature": (tuple(cols), unique_bool), "canonical_name": str, "alias_names": [str, ...]}
EXPECTED_INDEX_GROUPS = {
    "api_keys": [
        {
            "signature": (("tenant_id",), False),
            "canonical_name": "idx_api_keys_tenant",
            "alias_names": ["ix_api_keys_tenant_id"],
        },
    ],
    "runs": [
        {
            "signature": (("status", "lease_expires_at"), False),
            "canonical_name": "idx_runs_status_lease",
            "alias_names": [],
        },
        {
            "signature": (("tenant_id", "created_at"), False),
            "canonical_name": "idx_runs_tenant_created",
            "alias_names": [],
        },
    ],
    "tenant_plans": [
        {
            "signature": (("tenant_id", "effective_from", "effective_to"), False),
            "canonical_name": "idx_tenant_plans_effective",
            "alias_names": [],
        },
        {
            "signature": (("tenant_id", "status"), False),
            "canonical_name": "idx_tenant_plans_tenant_status",
            "alias_names": [],
        },
    ],
    "tenant_usage_daily": [
        {
            "signature": (("tenant_id", "usage_date"), True),
            "canonical_name": "idx_tenant_usage_daily_tenant_date",
            "alias_names": [],
        },
    ],
}

# BIGINT identity check tables
IDENTITY_TABLES = {"tenant_plans": "id", "tenant_usage_daily": "id"}


# --- HELPER FUNCTIONS ---

def debug(msg: str) -> None:
    """Print debug message to stderr if DEBUG=1."""
    if os.getenv("DEBUG") == "1":
        print(f"[DEBUG] {msg}", file=sys.stderr)


def error_exit(code: str, exit_code: int, failures: list[dict[str, str]] | None = None) -> None:
    """Print error code and exit."""
    if os.getenv("JSON_OUTPUT") == "1":
        report = {
            "status": "ERROR" if exit_code == 2 else "FAIL",
            "exit_code": exit_code,
            "error_code": code,
            "failures": failures or [],
        }
        print(json.dumps(report, indent=2))
    else:
        print(f"ERROR:{code}")
    sys.exit(exit_code)


def build_db_engine(database_url: str) -> Engine:
    """Build SQLAlchemy engine with Spec Lock policy."""
    if USE_SSOT_ENGINE:
        debug("Using SSOT engine builder (dpp_api.db.engine)")
        return build_engine(database_url)
    else:
        debug("Using fallback engine (NullPool + pool_pre_ping)")
        connect_args = {}
        if "supabase.com" in database_url or "supabase.co" in database_url:
            if "sslmode=" not in database_url:
                connect_args["sslmode"] = "require"
        return create_engine(
            database_url,
            poolclass=NullPool,
            pool_pre_ping=True,
            connect_args=connect_args,
            echo=False,
        )


def check_migrations_applied(engine: Engine, schema: str) -> None:
    """Verify alembic_version table exists and has at least 1 version."""
    try:
        with engine.connect() as conn:
            result = conn.execute(
                text(f"SELECT version_num FROM {schema}.alembic_version")
            ).fetchall()
            if not result:
                debug("alembic_version table is empty")
                error_exit("MIGRATIONS_NOT_APPLIED", 5)
            debug(f"Migrations applied: {len(result)} version(s)")
    except SQLAlchemyError as e:
        debug(f"alembic_version check failed: {e}")
        error_exit("MIGRATIONS_NOT_APPLIED", 5)


def check_table_columns(
    engine: Engine, schema: str, table: str, expected_cols: list[tuple[str, str, str]]
) -> None:
    """Verify table columns match expected spec (ordinal_position, udt_name, is_nullable)."""
    query = text(
        """
        SELECT ordinal_position, column_name, udt_name, is_nullable, is_identity, column_default
        FROM information_schema.columns
        WHERE table_schema = :schema AND table_name = :table
        ORDER BY ordinal_position
        """
    )
    with engine.connect() as conn:
        result = conn.execute(query, {"schema": schema, "table": table}).fetchall()

    actual_cols = [(row[1], row[2], row[3]) for row in result]
    if actual_cols != expected_cols:
        debug(f"Column mismatch in {table}")
        debug(f"  Expected: {expected_cols}")
        debug(f"  Actual:   {actual_cols}")
        error_exit("SCHEMA_DRIFT", 3)

    # STRICT_IDENTITY_CHECK for BIGINT autoincrement
    if table in IDENTITY_TABLES:
        id_col = IDENTITY_TABLES[table]
        id_row = next((r for r in result if r[1] == id_col), None)
        if not id_row:
            debug(f"Identity column {id_col} not found in {table}")
            error_exit("IDENTITY_DRIFT", 3)
        is_identity = id_row[4]
        column_default = id_row[5]
        if is_identity != "YES" and (
            not column_default or "nextval(" not in column_default.lower()
        ):
            debug(
                f"Identity check failed for {table}.{id_col}: is_identity={is_identity}, default={column_default}"
            )
            error_exit("IDENTITY_DRIFT", 3)


def check_primary_key(engine: Engine, schema: str, table: str, expected_pk: list[str]) -> None:
    """Verify primary key columns match expected."""
    inspector = inspect(engine)
    pk_constraint = inspector.get_pk_constraint(table, schema=schema)
    actual_pk = pk_constraint.get("constrained_columns", [])
    if set(actual_pk) != set(expected_pk):
        debug(f"PK mismatch in {table}")
        debug(f"  Expected: {expected_pk}")
        debug(f"  Actual:   {actual_pk}")
        error_exit("PK_DRIFT", 3)


def check_unique_constraints(
    engine: Engine, schema: str, table: str, expected_uqs: list[tuple[str, list[str]]]
) -> None:
    """Verify unique constraints match expected (name + columns)."""
    inspector = inspect(engine)
    actual_uqs = inspector.get_unique_constraints(table, schema=schema)
    actual_map = {uq["name"]: sorted(uq["column_names"]) for uq in actual_uqs}

    for uq_name, uq_cols in expected_uqs:
        if uq_name not in actual_map:
            debug(f"Missing unique constraint {uq_name} in {table}")
            error_exit("UQ_DRIFT", 3)
        if sorted(uq_cols) != actual_map[uq_name]:
            debug(f"Unique constraint mismatch {uq_name} in {table}")
            debug(f"  Expected: {sorted(uq_cols)}")
            debug(f"  Actual:   {actual_map[uq_name]}")
            error_exit("UQ_DRIFT", 3)


def check_indexes(
    engine: Engine, schema: str, table: str, expected_groups: list[dict[str, Any]], mode: str
) -> None:
    """Verify indexes match expected with dup toggle.

    Args:
        mode: "strict" or "relaxed"
    """
    inspector = inspect(engine)
    indexes = inspector.get_indexes(table, schema=schema)

    # Build signature map: {(tuple(cols), unique): [names]}
    sig_map: dict[tuple[tuple[str, ...], bool], list[str]] = {}
    for idx in indexes:
        cols = tuple(idx["column_names"])
        unique = idx["unique"]
        sig = (cols, unique)
        if sig not in sig_map:
            sig_map[sig] = []
        sig_map[sig].append(idx["name"])

    debug(f"Index signature map for {table}: {sig_map}")

    if mode == "strict":
        # STRICT: Each expected signature must have exactly 1 index with canonical name
        expected_sigs = {tuple(g["signature"]) for g in expected_groups}

        for group in expected_groups:
            sig = tuple(group["signature"])
            canonical = group["canonical_name"]
            if sig not in sig_map:
                debug(f"Missing index signature {sig} in {table}")
                error_exit("INDEX_DRIFT", 3)
            names = sig_map[sig]
            if len(names) != 1:
                debug(f"Index duplicate detected for signature {sig} in {table}: {names}")
                error_exit("INDEX_DUP_DRIFT", 3)
            if names[0] != canonical:
                debug(
                    f"Index name mismatch for signature {sig} in {table}: expected {canonical}, got {names[0]}"
                )
                error_exit("INDEX_DRIFT", 3)

        # Extra signatures = DRIFT
        extra_sigs = set(sig_map.keys()) - expected_sigs
        if extra_sigs:
            debug(f"Extra index signatures in {table}: {extra_sigs}")
            error_exit("INDEX_DRIFT", 3)

    else:  # relaxed
        # RELAXED: Each expected signature must have >=1 index with canonical or alias name
        for group in expected_groups:
            sig = tuple(group["signature"])
            canonical = group["canonical_name"]
            aliases = group.get("alias_names", [])
            allowed_names = {canonical} | set(aliases)

            if sig not in sig_map:
                debug(f"Missing index signature {sig} in {table}")
                error_exit("INDEX_DRIFT", 3)
            names = sig_map[sig]
            if not any(name in allowed_names for name in names):
                debug(
                    f"Index name mismatch for signature {sig} in {table}: expected one of {allowed_names}, got {names}"
                )
                error_exit("INDEX_DRIFT", 3)

            # Warn about duplicates but don't fail
            if len(names) > 1:
                debug(f"[WARN] Index duplicate for signature {sig} in {table}: {names} (allowed in relaxed mode)")

        # Extra signatures = WARN only
        expected_sigs = {tuple(g["signature"]) for g in expected_groups}
        extra_sigs = set(sig_map.keys()) - expected_sigs
        if extra_sigs:
            debug(f"[WARN] Extra index signatures in {table}: {extra_sigs} (allowed in relaxed mode)")


def check_rls_enabled(engine: Engine, schema: str, tables: list[str]) -> None:
    """Verify RLS is enabled on all tables (pg_class.relrowsecurity=true)."""
    query = text(
        """
        SELECT c.relname, c.relrowsecurity
        FROM pg_class c
        JOIN pg_namespace n ON n.oid = c.relnamespace
        WHERE n.nspname = :schema AND c.relname = ANY(:tables)
        ORDER BY c.relname
        """
    )
    with engine.connect() as conn:
        result = conn.execute(query, {"schema": schema, "tables": tables}).fetchall()

    rls_map = {row[0]: row[1] for row in result}

    for table in tables:
        if table not in rls_map:
            debug(f"Table {table} not found in pg_class (RLS check)")
            error_exit("RLS_CHECK_FAILED", 1)
        if not rls_map[table]:
            debug(f"RLS not enabled on {table} (relrowsecurity=false)")
            error_exit("RLS_DISABLED", 1)

    debug("RLS enabled on all tables")


def main() -> None:
    """Main smoke check logic."""
    # ENV check
    database_url = os.getenv("DATABASE_URL")
    if not database_url:
        error_exit("ENV_MISSING", 2, [{"code": "ENV_MISSING", "detail": "DATABASE_URL not set"}])

    # Redact password from debug output
    safe_url = database_url.split("@")[-1] if "@" in database_url else "***"
    debug(f"DATABASE_URL host: {safe_url}")

    schema = os.getenv("DATABASE_SCHEMA", "public")
    debug(f"Schema: {schema}")

    # Determine mode
    mode = "relaxed" if os.getenv("RELAXED") == "1" else "strict"
    debug(f"Index dup mode: {mode}")

    # Connect
    try:
        engine = build_db_engine(database_url)
        with engine.connect() as conn:
            conn.execute(text("SELECT 1"))
        debug("DB connection OK")
    except SQLAlchemyError as e:
        debug(f"DB connection failed: {e}")
        error_exit("DB_CONNECT", 4)

    # Migrations check
    check_migrations_applied(engine, schema)

    # Schema checks
    all_tables = list(EXPECTED_TABLE_SPECS.keys())
    for table, expected_cols in EXPECTED_TABLE_SPECS.items():
        debug(f"Checking table: {table}")
        check_table_columns(engine, schema, table, expected_cols)
        check_primary_key(engine, schema, table, EXPECTED_PK[table])

        if table in EXPECTED_UNIQUE_CONSTRAINTS:
            check_unique_constraints(
                engine, schema, table, EXPECTED_UNIQUE_CONSTRAINTS[table]
            )

        if table in EXPECTED_INDEX_GROUPS:
            check_indexes(engine, schema, table, EXPECTED_INDEX_GROUPS[table], mode)

    # RLS check
    debug("Checking RLS enabled on all tables...")
    check_rls_enabled(engine, schema, all_tables)

    # Collect metadata for JSON output
    if os.getenv("JSON_OUTPUT") == "1" or os.getenv("SAVE_EVIDENCE") == "1":
        with engine.connect() as conn:
            meta_result = conn.execute(
                text(
                    "SELECT current_user, current_database(), version()"
                )
            ).fetchone()
            current_user = meta_result[0] if meta_result else "unknown"
            current_database = meta_result[1] if meta_result else "unknown"
            server_version = meta_result[2] if meta_result else "unknown"

        report = {
            "status": "PASS",
            "exit_code": 0,
            "meta": {
                "timestamp_utc": datetime.now(timezone.utc).isoformat(),
                "current_user": current_user,
                "current_database": current_database,
                "server_version": server_version,
            },
            "checks": {
                "tables": len(all_tables),
                "columns": sum(len(cols) for cols in EXPECTED_TABLE_SPECS.values()),
                "constraints": len(EXPECTED_UNIQUE_CONSTRAINTS),
                "indexes": sum(len(groups) for groups in EXPECTED_INDEX_GROUPS.values()),
                "rls": "enabled on all tables",
                "mode": mode,
            },
            "failures": [],
        }

        if os.getenv("JSON_OUTPUT") == "1":
            print(json.dumps(report, indent=2))

        if os.getenv("SAVE_EVIDENCE") == "1":
            evidence_dir = Path(__file__).parent.parent / "evidence"
            evidence_dir.mkdir(exist_ok=True)
            timestamp = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S")
            evidence_file = evidence_dir / f"db_smoke_check_{timestamp}.json"
            with open(evidence_file, "w") as f:
                json.dump(report, f, indent=2)
            if os.getenv("JSON_OUTPUT") != "1":
                print(f"Evidence saved: {evidence_file}")
    else:
        print("OK")

    sys.exit(0)


if __name__ == "__main__":
    main()
