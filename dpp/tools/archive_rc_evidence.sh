#!/usr/bin/env bash
# Archive RC Evidence Pack (Local 2 runs + CI 1 run + Docs snapshot)
# Purpose: Bundle local and CI evidence into single archive folder for audit/compliance

set -Eeuo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd "$SCRIPT_DIR/.." && pwd)"

# Colors
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
RED='\033[0;31m'
NC='\033[0m'

# Parse arguments/environment
CI_RUN_ID="${CI_RUN_ID:-${1:-}}"
ARCHIVE_DATE="${ARCHIVE_DATE:-$(date +%Y%m%d)}"
ARCHIVE_TAG="${ARCHIVE_TAG:-v0.4}"

# Validate required inputs
if [ -z "$CI_RUN_ID" ]; then
  echo -e "${RED}ERROR: CI_RUN_ID is required${NC}"
  echo "Usage: CI_RUN_ID=<run_id> $0"
  echo "   or: $0 <run_id>"
  exit 1
fi

# Archive directory
ARCHIVE_DIR="$REPO_ROOT/evidence/rc-${ARCHIVE_TAG}-${ARCHIVE_DATE}"

echo -e "${GREEN}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"
echo -e "${GREEN}RC Evidence Pack Archive${NC}"
echo -e "${GREEN}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"
echo "Archive directory: $ARCHIVE_DIR"
echo "CI run ID: $CI_RUN_ID"
echo ""

# Step 1: Get commit SHA
echo -e "${YELLOW}[1/6] Capturing commit SHA...${NC}"
COMMIT_SHA=$(git -C "$REPO_ROOT" rev-parse HEAD)
echo "Commit: $COMMIT_SHA"

# Step 2: Create archive structure
echo -e "${YELLOW}[2/6] Creating archive directory structure...${NC}"
mkdir -p "$ARCHIVE_DIR/local"
mkdir -p "$ARCHIVE_DIR/ci/run_${CI_RUN_ID}"
mkdir -p "$ARCHIVE_DIR/docs_snapshot"

# Step 3: Copy latest 2 local evidence directories
echo -e "${YELLOW}[3/6] Copying latest 2 local evidence runs...${NC}"
cd "$REPO_ROOT"
mapfile -t local_dirs < <(ls -1dt evidence/01_ci/* 2>/dev/null | head -2)

if [ ${#local_dirs[@]} -lt 2 ]; then
  echo -e "${RED}WARNING: Less than 2 local evidence directories found (found: ${#local_dirs[@]})${NC}"
  echo "Expected at least 2 runs (clean + rerun)"
fi

LOCAL_TS_ARRAY=()
for local_dir in "${local_dirs[@]}"; do
  basename_dir=$(basename "$local_dir")
  echo "  Copying: $local_dir -> $ARCHIVE_DIR/local/$basename_dir"
  cp -r "$local_dir" "$ARCHIVE_DIR/local/$basename_dir"
  LOCAL_TS_ARRAY+=("\"$basename_dir\"")
done

# Step 4: Check gh CLI authentication
echo -e "${YELLOW}[4/6] Checking GitHub CLI authentication...${NC}"
if ! command -v gh &> /dev/null; then
  echo -e "${RED}ERROR: GitHub CLI (gh) is not installed${NC}"
  echo "Install: https://cli.github.com/"
  exit 1
fi

if ! gh auth status &> /dev/null; then
  echo -e "${RED}ERROR: GitHub CLI is not authenticated${NC}"
  echo "Run: gh auth login"
  exit 1
fi
echo "GitHub CLI: authenticated"

# Step 5: Download CI artifact
echo -e "${YELLOW}[5/6] Downloading CI artifact (run ID: $CI_RUN_ID)...${NC}"
cd "$REPO_ROOT"
gh run download "$CI_RUN_ID" -D "$ARCHIVE_DIR/ci/run_${CI_RUN_ID}" || {
  echo -e "${RED}ERROR: Failed to download CI artifact${NC}"
  echo "Verify run ID exists: gh run view $CI_RUN_ID"
  exit 1
}
echo "CI artifact downloaded successfully"

# Step 6: Copy docs/workflow snapshots
echo -e "${YELLOW}[6/6] Creating docs snapshot...${NC}"
cp "$REPO_ROOT/docs/RC_MASTER_CHECKLIST.md" "$ARCHIVE_DIR/docs_snapshot/" 2>/dev/null || true
cp "$REPO_ROOT/tools/README_RC_GATES.md" "$ARCHIVE_DIR/docs_snapshot/" 2>/dev/null || true
cp "$REPO_ROOT/.github/workflows/rc_gates.yml" "$ARCHIVE_DIR/docs_snapshot/" 2>/dev/null || true

# Create manifest.json
echo -e "${YELLOW}Creating manifest.json...${NC}"
LOCAL_TS_JSON="[$(IFS=,; echo "${LOCAL_TS_ARRAY[*]}")]"
CREATED_AT_UTC=$(date -u +"%Y-%m-%dT%H:%M:%SZ")

cat > "$ARCHIVE_DIR/manifest.json" <<EOF
{
  "archive_dir": "$(basename "$ARCHIVE_DIR")",
  "archive_tag": "$ARCHIVE_TAG",
  "archive_date": "$ARCHIVE_DATE",
  "commit_sha": "$COMMIT_SHA",
  "local_evidence_dirs": $LOCAL_TS_JSON,
  "ci_run_id": "$CI_RUN_ID",
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
echo "  - local/ (${#local_dirs[@]} runs)"
echo "  - ci/run_${CI_RUN_ID}/"
echo "  - docs_snapshot/"
