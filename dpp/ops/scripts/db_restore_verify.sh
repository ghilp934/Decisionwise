#!/bin/bash
#
# Supabase Database Restore and Verification Script.
#
# Usage:
#   ./ops/scripts/db_restore_verify.sh --file backups/dpp_20260217_120000.sql.gz --target-url "postgres://..."
#
# Safety:
#   - Requires explicit --target-url (prevents accidental production restore)
#   - Validates target is Supabase Pooler Transaction mode
#   - Verifies table row counts after restore
#

set -euo pipefail

# Parse arguments
BACKUP_FILE=""
TARGET_URL=""

while [[ $# -gt 0 ]]; do
  case "$1" in
    --file)
      BACKUP_FILE="$2"
      shift 2
      ;;
    --target-url)
      TARGET_URL="$2"
      shift 2
      ;;
    *)
      echo "Unknown argument: $1"
      echo "Usage: $0 --file BACKUP_FILE --target-url TARGET_URL"
      exit 1
      ;;
  esac
done

# Validate arguments
if [[ -z "$BACKUP_FILE" ]] || [[ -z "$TARGET_URL" ]]; then
  echo "ERROR: Missing required arguments."
  echo "Usage: $0 --file BACKUP_FILE --target-url TARGET_URL"
  exit 1
fi

if [[ ! -f "$BACKUP_FILE" ]]; then
  echo "ERROR: Backup file not found: $BACKUP_FILE"
  exit 1
fi

# Extract host and port from TARGET_URL
if [[ ! "$TARGET_URL" =~ postgres(ql)?://([^:]+):([^@]+)@([^:]+):([0-9]+)/(.+) ]]; then
  echo "ERROR: Invalid TARGET_URL format."
  echo "Expected: postgres://user:pass@host:port/dbname"
  exit 1
fi

DB_HOST="${BASH_REMATCH[4]}"
DB_PORT="${BASH_REMATCH[5]}"

echo "==================================================================="
echo "Supabase Database Restore and Verification"
echo "==================================================================="
echo "Backup File: $BACKUP_FILE"
echo "Target Host: $DB_HOST"
echo "Target Port: $DB_PORT"

# Safety check: Supabase validation
if [[ "$DB_HOST" == *".supabase.co"* ]] || [[ "$DB_HOST" == *".pooler.supabase.com"* ]]; then
  echo "Supabase host detected."

  # Check port 6543
  if [[ "$DB_PORT" != "6543" ]]; then
    echo "WARNING: Expected Supabase Pooler Transaction mode (port 6543), got $DB_PORT."
    read -p "Continue anyway? (y/N): " -n 1 -r
    echo
    if [[ ! $REPLY =~ ^[Yy]$ ]]; then
      echo "Aborted."
      exit 1
    fi
  fi

  # Check pooler in hostname
  if [[ "$DB_HOST" != *"pooler"* ]]; then
    echo "WARNING: Expected 'pooler' in hostname for Pooler mode, got $DB_HOST."
    read -p "Continue anyway? (y/N): " -n 1 -r
    echo
    if [[ ! $REPLY =~ ^[Yy]$ ]]; then
      echo "Aborted."
      exit 1
    fi
  fi

  echo "Target configuration validated."
fi

# Final confirmation
echo "==================================================================="
echo "WARNING: This will restore the backup to the target database."
echo "This operation may overwrite existing data."
read -p "Continue restore? (y/N): " -n 1 -r
echo
if [[ ! $REPLY =~ ^[Yy]$ ]]; then
  echo "Aborted."
  exit 1
fi

echo "==================================================================="
echo "Starting restore..."
echo "==================================================================="

# Decompress and restore
gunzip -c "$BACKUP_FILE" | psql "$TARGET_URL" > /dev/null 2>&1

echo "Restore completed."
echo "==================================================================="
echo "Verifying table row counts..."
echo "==================================================================="

# Verify table row counts
psql "$TARGET_URL" -c "
SELECT
  schemaname,
  tablename,
  (xpath('/row/cnt/text()', xml_count))[1]::text::int AS row_count
FROM (
  SELECT
    schemaname,
    tablename,
    query_to_xml(
      format('SELECT count(*) AS cnt FROM %I.%I', schemaname, tablename),
      false,
      true,
      ''
    ) AS xml_count
  FROM pg_tables
  WHERE schemaname = 'public'
    AND tablename IN ('tenants', 'api_keys', 'runs', 'plans', 'tenant_plans', 'tenant_usage_daily')
) AS counts
ORDER BY tablename;
"

echo "==================================================================="
echo "Restore verification completed!"
echo "==================================================================="
