#!/bin/bash
#
# Supabase Database Backup Script (pg_dump wrapper).
#
# Usage:
#   ./ops/scripts/db_backup_pgdump.sh
#   ./ops/scripts/db_backup_pgdump.sh --url "postgres://..."
#
# Environment:
#   DATABASE_URL: Database connection string (required if --url not provided)
#
# Output:
#   backups/dpp_{timestamp}.sql.gz
#
# Safety:
#   - Validates Supabase Pooler Transaction mode (port 6543, pooler host)
#   - Requires confirmation for non-Supabase databases
#

set -euo pipefail

# Parse arguments
DB_URL="${DATABASE_URL:-}"
while [[ $# -gt 0 ]]; do
  case "$1" in
    --url)
      DB_URL="$2"
      shift 2
      ;;
    *)
      echo "Unknown argument: $1"
      echo "Usage: $0 [--url DATABASE_URL]"
      exit 1
      ;;
  esac
done

# Validate DATABASE_URL
if [[ -z "$DB_URL" ]]; then
  echo "ERROR: DATABASE_URL not set and --url not provided."
  echo "Usage: $0 [--url DATABASE_URL]"
  exit 1
fi

# Extract host and port from DATABASE_URL
# Format: postgres://user:pass@host:port/dbname
if [[ ! "$DB_URL" =~ postgres(ql)?://([^:]+):([^@]+)@([^:]+):([0-9]+)/(.+) ]]; then
  echo "ERROR: Invalid DATABASE_URL format."
  echo "Expected: postgres://user:pass@host:port/dbname"
  exit 1
fi

DB_HOST="${BASH_REMATCH[4]}"
DB_PORT="${BASH_REMATCH[5]}"

echo "==================================================================="
echo "Supabase Database Backup (pg_dump)"
echo "==================================================================="
echo "Host: $DB_HOST"
echo "Port: $DB_PORT"

# Safety check: Supabase validation
if [[ "$DB_HOST" == *".supabase.co"* ]] || [[ "$DB_HOST" == *".pooler.supabase.com"* ]]; then
  echo "Supabase host detected."

  # Check port 6543 (Pooler Transaction mode)
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

  echo "Supabase configuration validated."
else
  echo "WARNING: Non-Supabase database detected."
  read -p "Continue backup? (y/N): " -n 1 -r
  echo
  if [[ ! $REPLY =~ ^[Yy]$ ]]; then
    echo "Aborted."
    exit 1
  fi
fi

# Create backups directory
BACKUP_DIR="$(dirname "$0")/../../backups"
mkdir -p "$BACKUP_DIR"

# Generate backup filename with timestamp
TIMESTAMP=$(date +"%Y%m%d_%H%M%S")
BACKUP_FILE="$BACKUP_DIR/dpp_${TIMESTAMP}.sql.gz"

echo "==================================================================="
echo "Starting backup..."
echo "Output: $BACKUP_FILE"
echo "==================================================================="

# Run pg_dump with compression
# Note: pg_dump reads connection info from DATABASE_URL environment variable
export PGPASSWORD="${DB_URL#*://}"
export PGPASSWORD="${PGPASSWORD#*:}"
export PGPASSWORD="${PGPASSWORD%%@*}"

pg_dump "$DB_URL" --no-owner --no-acl | gzip > "$BACKUP_FILE"

echo "==================================================================="
echo "Backup completed successfully!"
echo "File: $BACKUP_FILE"
echo "Size: $(du -h "$BACKUP_FILE" | cut -f1)"
echo "==================================================================="
