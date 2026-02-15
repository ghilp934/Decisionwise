#!/usr/bin/env bash
# RC Double Run + CI Trigger + Auto Archive (All-in-one)
# Purpose: Execute local 2x, trigger CI, wait, and archive all evidence automatically

set -Eeuo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd "$SCRIPT_DIR/.." && pwd)"

# Colors
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
RED='\033[0;31m'
BLUE='\033[0;34m'
NC='\033[0m'

# Configuration
WORKFLOW_NAME="RC Gates"
ARCHIVE_TAG="${ARCHIVE_TAG:-v0.4}"
ARCHIVE_DATE="${ARCHIVE_DATE:-$(date +%Y%m%d)}"

echo -e "${BLUE}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"
echo -e "${BLUE}RC Double + CI + Archive (Full Pipeline)${NC}"
echo -e "${BLUE}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"
echo ""

# Preflight checks
echo -e "${YELLOW}[Preflight] Checking prerequisites...${NC}"

# Check current branch
CURRENT_BRANCH=$(git -C "$REPO_ROOT" rev-parse --abbrev-ref HEAD)
if [ "$CURRENT_BRANCH" != "master" ] && [ "$CURRENT_BRANCH" != "main" ]; then
  echo -e "${RED}ERROR: Must be on main/master branch (current: $CURRENT_BRANCH)${NC}"
  echo "Reason: CI workflow_dispatch can only trigger from default branch"
  echo "Action: Merge your PR first, then run this script from main/master"
  exit 1
fi
echo "✓ Branch: $CURRENT_BRANCH"

# Check if workflow file exists
if [ ! -f "$REPO_ROOT/.github/workflows/rc_gates.yml" ]; then
  echo -e "${RED}ERROR: Workflow file not found: .github/workflows/rc_gates.yml${NC}"
  echo "Action: Ensure RC Gates workflow is merged to main/master"
  exit 1
fi
echo "✓ Workflow file exists"

# Check gh CLI
if ! command -v gh &> /dev/null; then
  echo -e "${RED}ERROR: GitHub CLI (gh) not found${NC}"
  echo "Install: https://cli.github.com/"
  exit 1
fi

if ! gh auth status &> /dev/null; then
  echo -e "${RED}ERROR: GitHub CLI not authenticated${NC}"
  echo "Run: gh auth login"
  exit 1
fi
echo "✓ GitHub CLI authenticated"

# Verify workflow exists on remote
if ! gh workflow list | grep -q "$WORKFLOW_NAME"; then
  echo -e "${RED}ERROR: Workflow '$WORKFLOW_NAME' not found on remote${NC}"
  echo "Available workflows:"
  gh workflow list
  echo ""
  echo "Action: Push .github/workflows/rc_gates.yml to main/master first"
  exit 1
fi
echo "✓ Workflow '$WORKFLOW_NAME' found on remote"

echo ""

# Step 1: Capture baseline commit
echo -e "${GREEN}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"
echo -e "${GREEN}[1/5] Capture baseline commit${NC}"
echo -e "${GREEN}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"
COMMIT_SHA=$(git -C "$REPO_ROOT" rev-parse HEAD)
echo "Commit: $COMMIT_SHA"
echo ""

# Step 2: Local clean run
echo -e "${GREEN}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"
echo -e "${GREEN}[2/5] Local clean run (docker down --volumes)${NC}"
echo -e "${GREEN}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"
cd "$REPO_ROOT"
docker compose -f infra/docker-compose.yml down --volumes --remove-orphans
echo ""
bash tools/run_rc_gates.sh
echo ""

# Step 3: Local rerun (no cleanup)
echo -e "${GREEN}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"
echo -e "${GREEN}[3/5] Local rerun (no cleanup)${NC}"
echo -e "${GREEN}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"
bash tools/run_rc_gates.sh
echo ""

# Step 4: Check local results (PASS guard)
echo -e "${GREEN}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"
echo -e "${GREEN}[4/5] Verify local runs (PASS guard)${NC}"
echo -e "${GREEN}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"

mapfile -t dirs < <(ls -1dt evidence/01_ci/* 2>/dev/null | head -2)

if [ ${#dirs[@]} -lt 2 ]; then
  echo -e "${RED}ERROR: Less than 2 local evidence directories found${NC}"
  echo "Expected: 2 (clean run + rerun)"
  exit 1
fi

FAIL_COUNT=0
for d in "${dirs[@]}"; do
  echo "Checking: $d"
  fail_line="$(grep -hE '^FAILED ' "$d/rc_run_stdout.log" "$d/rc_run_stderr.log" 2>/dev/null | head -1 || true)"
  if [ -n "$fail_line" ]; then
    echo -e "${RED}  FAIL: $(echo "$fail_line" | awk '{print $2}')${NC}"
    FAIL_COUNT=$((FAIL_COUNT + 1))
  else
    echo -e "${GREEN}  PASS${NC}"
  fi
done

if [ $FAIL_COUNT -gt 0 ]; then
  echo ""
  echo -e "${RED}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"
  echo -e "${RED}STOP: Local runs have $FAIL_COUNT failure(s)${NC}"
  echo -e "${RED}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"
  echo "Action: Fix failures before triggering CI or archiving"
  exit 1
fi

echo -e "${GREEN}✓ Both local runs PASSED${NC}"
echo ""

# Step 5: Trigger CI + wait + archive
echo -e "${GREEN}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"
echo -e "${GREEN}[5/5] Trigger CI + Wait + Archive${NC}"
echo -e "${GREEN}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"

# Trigger workflow
echo "Triggering workflow: '$WORKFLOW_NAME' on branch $CURRENT_BRANCH..."
gh workflow run "$WORKFLOW_NAME" --ref "$CURRENT_BRANCH"

# Wait a bit for workflow to appear
echo "Waiting 5 seconds for workflow to register..."
sleep 5

# Get latest run ID
echo "Fetching latest run ID..."
RUN_ID=$(gh run list -w "$WORKFLOW_NAME" --limit 1 --json databaseId -q '.[0].databaseId')

if [ -z "$RUN_ID" ]; then
  echo -e "${RED}ERROR: Failed to get run ID${NC}"
  echo "Check manually: gh run list -w '$WORKFLOW_NAME'"
  exit 1
fi

echo "CI Run ID: $RUN_ID"
echo "Watching: https://github.com/$(gh repo view --json nameWithOwner -q .nameWithOwner)/actions/runs/$RUN_ID"
echo ""

# Wait for completion
echo "Waiting for CI to complete (this may take several minutes)..."
if gh run watch "$RUN_ID" --exit-status; then
  echo -e "${GREEN}✓ CI run completed successfully${NC}"
else
  echo -e "${YELLOW}WARNING: CI run did not pass (exit status non-zero)${NC}"
  echo "Proceeding with archive anyway (for debugging)"
fi
echo ""

# Archive everything
echo -e "${BLUE}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"
echo -e "${BLUE}Archiving Evidence Pack${NC}"
echo -e "${BLUE}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"
CI_RUN_ID="$RUN_ID" ARCHIVE_TAG="$ARCHIVE_TAG" ARCHIVE_DATE="$ARCHIVE_DATE" \
  bash "$SCRIPT_DIR/archive_rc_evidence.sh"

echo ""
echo -e "${GREEN}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"
echo -e "${GREEN}✅ FULL PIPELINE COMPLETE${NC}"
echo -e "${GREEN}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"
echo ""
echo "Archive: evidence/rc-${ARCHIVE_TAG}-${ARCHIVE_DATE}/"
echo "Commit: $COMMIT_SHA"
echo "CI Run: $RUN_ID"
