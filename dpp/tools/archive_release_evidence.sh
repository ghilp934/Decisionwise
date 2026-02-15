#!/usr/bin/env bash
# Archive Release Evidence (RC Gates + Pilot Packet)
# Purpose: Download and archive CI artifacts from both workflows with event metadata

set -Eeuo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd "$SCRIPT_DIR/.." && pwd)"

# Colors
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
RED='\033[0;31m'
NC='\033[0m'

# Parse arguments
RC_GATES_RUN_ID="${RC_GATES_RUN_ID:-${1:-}}"
PILOT_RUN_ID="${PILOT_RUN_ID:-${2:-}}"
ARCHIVE_DATE="${ARCHIVE_DATE:-$(date +%Y%m%d)}"
ARCHIVE_TAG="${ARCHIVE_TAG:-v0.4}"

# Validate inputs
if [ -z "$RC_GATES_RUN_ID" ] || [ -z "$PILOT_RUN_ID" ]; then
  echo -e "${RED}ERROR: Both run IDs required${NC}"
  echo "Usage: RC_GATES_RUN_ID=<id1> PILOT_RUN_ID=<id2> $0"
  echo "   or: $0 <rc_gates_run_id> <pilot_run_id>"
  exit 1
fi

# Archive directory
ARCHIVE_DIR="$REPO_ROOT/evidence/rc-${ARCHIVE_TAG}-${ARCHIVE_DATE}"
META_DIR="$ARCHIVE_DIR/meta"

echo -e "${GREEN}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"
echo -e "${GREEN}Release Evidence Archive${NC}"
echo -e "${GREEN}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"
echo "Archive: $ARCHIVE_DIR"
echo "RC Gates Run ID: $RC_GATES_RUN_ID"
echo "Pilot Run ID: $PILOT_RUN_ID"
echo ""

# Create structure
echo -e "${YELLOW}[1/5] Creating archive structure...${NC}"
mkdir -p "$META_DIR"
mkdir -p "$ARCHIVE_DIR/ci/rc_gates_${RC_GATES_RUN_ID}"
mkdir -p "$ARCHIVE_DIR/ci/pilot_${PILOT_RUN_ID}"

# Capture commit SHA
echo -e "${YELLOW}[2/5] Capturing commit info...${NC}"
COMMIT_SHA=$(git -C "$REPO_ROOT" rev-parse HEAD)
echo "$COMMIT_SHA" > "$META_DIR/commit_sha.txt"
echo "Commit: $COMMIT_SHA"

# Check gh CLI
echo -e "${YELLOW}[3/5] Checking GitHub CLI...${NC}"
if ! command -v gh &> /dev/null; then
  echo -e "${RED}ERROR: gh CLI not installed${NC}"
  exit 1
fi

if ! gh auth status &> /dev/null; then
  echo -e "${RED}ERROR: gh CLI not authenticated${NC}"
  exit 1
fi
echo "✓ GitHub CLI ready"

# Function: Capture run metadata with event info
capture_run_meta() {
  local run_id="$1"
  local label="$2"

  echo "  Capturing $label metadata (run_id: $run_id)..."

  # Save full JSON metadata
  local json_file="$META_DIR/${label}_run.json"
  gh run view "$run_id" \
    --json event,headSha,headBranch,workflowName,conclusion,status,createdAt,updatedAt,url \
    > "$json_file" 2>/dev/null || {
    echo -e "${RED}ERROR: Failed to get run metadata for $run_id${NC}"
    return 1
  }

  # Extract event to separate file (human-readable)
  local event_file="$META_DIR/${label}_event.txt"
  if command -v jq &> /dev/null; then
    jq -r '.event // "unknown"' "$json_file" > "$event_file"
  else
    # Fallback: python one-liner
    python3 -c "import json,sys; print(json.load(open('$json_file')).get('event','unknown'))" > "$event_file" 2>/dev/null || echo "unknown" > "$event_file"
  fi

  # Legacy: save run_id and conclusion for backwards compat
  echo "$run_id" > "$META_DIR/${label}_run_id.txt"
  if command -v jq &> /dev/null; then
    jq -r '.conclusion // "unknown"' "$json_file" > "$META_DIR/${label}_conclusion.txt"
  else
    python3 -c "import json,sys; print(json.load(open('$json_file')).get('conclusion','unknown'))" > "$META_DIR/${label}_conclusion.txt" 2>/dev/null || echo "unknown" > "$META_DIR/${label}_conclusion.txt"
  fi

  echo "  ✓ $label metadata saved"
}

# Capture metadata
echo -e "${YELLOW}[4/5] Capturing workflow metadata...${NC}"
capture_run_meta "$RC_GATES_RUN_ID" "rc_gates"
capture_run_meta "$PILOT_RUN_ID" "rehearse_customer"

# Download artifacts
echo -e "${YELLOW}[5/5] Downloading CI artifacts...${NC}"

echo "  Downloading RC Gates artifacts..."
if ! gh run download "$RC_GATES_RUN_ID" -D "$ARCHIVE_DIR/ci/rc_gates_${RC_GATES_RUN_ID}"; then
  echo -e "${YELLOW}WARNING: No artifacts for RC Gates run $RC_GATES_RUN_ID${NC}"
fi

echo "  Downloading Pilot Packet artifacts..."
if ! gh run download "$PILOT_RUN_ID" -D "$ARCHIVE_DIR/ci/pilot_${PILOT_RUN_ID}"; then
  echo -e "${YELLOW}WARNING: No artifacts for Pilot run $PILOT_RUN_ID${NC}"
fi

# Create manifest
echo -e "${YELLOW}Creating manifest...${NC}"
CREATED_AT_UTC=$(date -u +"%Y-%m-%dT%H:%M:%SZ")

cat > "$ARCHIVE_DIR/manifest.json" <<EOF
{
  "archive_tag": "$ARCHIVE_TAG",
  "archive_date": "$ARCHIVE_DATE",
  "commit_sha": "$COMMIT_SHA",
  "rc_gates_run_id": "$RC_GATES_RUN_ID",
  "pilot_run_id": "$PILOT_RUN_ID",
  "created_at_utc": "$CREATED_AT_UTC"
}
EOF

echo -e "${GREEN}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"
echo -e "${GREEN}✅ ARCHIVE COMPLETE${NC}"
echo -e "${GREEN}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"
echo ""
echo "ARCHIVED: $ARCHIVE_DIR"
echo ""
echo "Contents:"
echo "  - manifest.json"
echo "  - meta/ (event tracking)"
echo "  - ci/rc_gates_${RC_GATES_RUN_ID}/"
echo "  - ci/pilot_${PILOT_RUN_ID}/"
echo ""
echo "Event metadata:"
echo "  RC Gates: $(cat "$META_DIR/rc_gates_event.txt")"
echo "  Pilot Packet: $(cat "$META_DIR/rehearse_customer_event.txt")"
echo ""
