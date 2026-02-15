#!/usr/bin/env bash
set -Eeuo pipefail

# ==============================================================================
# GitHub Ruleset: Apply Main Branch Protection (RC Gate)
# ==============================================================================
# 목적: master 브랜치를 RC Gates + Pilot Packet Rehearsal 없이 머지 불가로 잠금
# 실행: APPLY=1 bash tools/github/apply_ruleset_main.sh
#       PLAN_ONLY=1 bash tools/github/apply_ruleset_main.sh
# ==============================================================================

die() { echo "FATAL: $*" >&2; exit 1; }
log() { echo "[$(date '+%Y-%m-%d %H:%M:%S')] $*" >&2; }

trap 'die "Script failed at line $LINENO"' ERR

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd "$SCRIPT_DIR/../.." && pwd)"
cd "$REPO_ROOT"

# 모드 설정
PLAN_ONLY="${PLAN_ONLY:-}"
APPLY="${APPLY:-}"

if [ -n "$APPLY" ] && [ -n "$PLAN_ONLY" ]; then
  die "Cannot set both APPLY and PLAN_ONLY"
fi

if [ -z "$APPLY" ] && [ -z "$PLAN_ONLY" ]; then
  log "No mode specified. Defaulting to PLAN_ONLY=1"
  PLAN_ONLY="1"
fi

MODE="PLAN"
if [ -n "$APPLY" ]; then
  MODE="APPLY"
fi

log "Mode: $MODE"

# Evidence 디렉토리
TIMESTAMP=$(date +%Y%m%d_%H%M%S)
EVDIR="evidence/github_rules/$TIMESTAMP"
mkdir -p "$EVDIR"

log "Evidence Dir: $EVDIR"

# ------------------------------------------------------------------------------
# 1. GitHub CLI 및 인증 확인
# ------------------------------------------------------------------------------
if ! command -v gh >/dev/null 2>&1; then
  die "gh CLI not found. Install: https://cli.github.com/"
fi

if ! gh auth status >/dev/null 2>&1; then
  die "gh not authenticated. Run: gh auth login"
fi

# Repository 정보 감지
REPO_INFO=$(gh repo view --json nameWithOwner,defaultBranchRef 2>/dev/null || echo "")
if [ -z "$REPO_INFO" ]; then
  die "Failed to detect repository. Run from within a Git repository."
fi

OWNER_REPO=$(echo "$REPO_INFO" | grep -oP '"nameWithOwner":\s*"\K[^"]+' || echo "")
DEFAULT_BRANCH=$(echo "$REPO_INFO" | grep -oP '"name":\s*"\K[^"]+' | head -1 || echo "master")

if [ -z "$OWNER_REPO" ]; then
  die "Failed to parse repository owner/name"
fi

log "Repository: $OWNER_REPO"
log "Default Branch: $DEFAULT_BRANCH"

echo "Repository: $OWNER_REPO" > "$EVDIR/repo_info.txt"
echo "Default Branch: $DEFAULT_BRANCH" >> "$EVDIR/repo_info.txt"

# ------------------------------------------------------------------------------
# 2. SSOT JSON 로드
# ------------------------------------------------------------------------------
SSOT_JSON="ops/github/ruleset_main.json"
if [ ! -f "$SSOT_JSON" ]; then
  die "SSOT JSON not found: $SSOT_JSON"
fi

log "Loading SSOT: $SSOT_JSON"
cp "$SSOT_JSON" "$EVDIR/ruleset_ssot.json"

# Default branch를 SSOT에서 업데이트
RULESET_PAYLOAD=$(cat "$SSOT_JSON" | sed "s|refs/heads/master|refs/heads/$DEFAULT_BRANCH|g")

# ------------------------------------------------------------------------------
# 3. 기존 Ruleset 조회 (before)
# ------------------------------------------------------------------------------
log "Fetching existing rulesets..."

gh api "repos/$OWNER_REPO/rulesets" --jq '.' > "$EVDIR/before.json" 2>"$EVDIR/api_error.log" || true

EXISTING_RULESET_ID=$(cat "$EVDIR/before.json" | grep -A 10 '"name":\s*"decisionproof-main-rc-gate"' | grep -oP '"id":\s*\K\d+' | head -1 || echo "")

if [ -n "$EXISTING_RULESET_ID" ]; then
  log "Existing ruleset found: ID=$EXISTING_RULESET_ID"
  echo "$EXISTING_RULESET_ID" > "$EVDIR/existing_id.txt"
else
  log "No existing ruleset found. Will create new one."
fi

# ------------------------------------------------------------------------------
# 4. PLAN_ONLY: 출력만
# ------------------------------------------------------------------------------
if [ "$MODE" = "PLAN" ]; then
  log "PLAN_ONLY mode: No changes will be applied."

  echo "$RULESET_PAYLOAD" | jq '.' > "$EVDIR/planned_ruleset.json"

  cat > "$EVDIR/summary.txt" <<EOF
================================================================================
GitHub Ruleset: Main Branch Protection - PLAN ONLY
================================================================================

Repository: $OWNER_REPO
Default Branch: $DEFAULT_BRANCH
Mode: PLAN (no changes applied)

Existing Ruleset: $([ -n "$EXISTING_RULESET_ID" ] && echo "ID=$EXISTING_RULESET_ID" || echo "None")
Action: $([ -n "$EXISTING_RULESET_ID" ] && echo "UPDATE" || echo "CREATE")

SSOT: $SSOT_JSON
Evidence: $EVDIR

Required Checks:
  - RC Gates (Linux)
  - rehearse-customer

To apply:
  APPLY=1 bash tools/github/apply_ruleset_main.sh

================================================================================
EOF

  cat "$EVDIR/summary.txt"
  exit 0
fi

# ------------------------------------------------------------------------------
# 5. APPLY: 실제 적용
# ------------------------------------------------------------------------------
log "APPLY mode: Applying ruleset..."

if [ -n "$EXISTING_RULESET_ID" ]; then
  # Update existing ruleset
  log "Updating ruleset ID=$EXISTING_RULESET_ID"

  echo "gh api --method PUT repos/$OWNER_REPO/rulesets/$EXISTING_RULESET_ID" > "$EVDIR/cmd.txt"
  echo "$RULESET_PAYLOAD" | gh api --method PUT "repos/$OWNER_REPO/rulesets/$EXISTING_RULESET_ID" --input - > "$EVDIR/after.json" 2>"$EVDIR/stderr.log"

  log "Ruleset updated successfully"
else
  # Create new ruleset
  log "Creating new ruleset"

  echo "gh api --method POST repos/$OWNER_REPO/rulesets" > "$EVDIR/cmd.txt"
  echo "$RULESET_PAYLOAD" | gh api --method POST "repos/$OWNER_REPO/rulesets" --input - > "$EVDIR/after.json" 2>"$EVDIR/stderr.log"

  NEW_ID=$(cat "$EVDIR/after.json" | grep -oP '"id":\s*\K\d+' | head -1 || echo "")
  log "Ruleset created successfully: ID=$NEW_ID"
  echo "$NEW_ID" > "$EVDIR/new_id.txt"
fi

# ------------------------------------------------------------------------------
# 6. Summary
# ------------------------------------------------------------------------------
cat > "$EVDIR/summary.txt" <<EOF
================================================================================
GitHub Ruleset: Main Branch Protection - APPLIED
================================================================================

Repository: $OWNER_REPO
Default Branch: $DEFAULT_BRANCH
Mode: APPLY

Action: $([ -n "$EXISTING_RULESET_ID" ] && echo "UPDATE (ID=$EXISTING_RULESET_ID)" || echo "CREATE")
Status: SUCCESS

SSOT: $SSOT_JSON
Evidence: $EVDIR

Required Checks:
  - RC Gates (Linux)
  - rehearse-customer

Rules Applied:
  ✅ Pull request (1 approval, conversation resolution)
  ✅ Required status checks (strict: true)
  ✅ Block force pushes
  ✅ Block deletions

Verify:
  bash tools/github/verify_branch_rules.sh

================================================================================
EOF

cat "$EVDIR/summary.txt"

log "✅ Ruleset applied successfully"
log "Evidence: $EVDIR"
