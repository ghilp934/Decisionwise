#!/usr/bin/env bash
# Rollback Drill: Undo Deployment + Re-test
# Purpose: Practice rollback to previous Known-Good state and verify

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
DATE_DIR=$(date +%Y%m%d)
EVIDENCE_DIR="$REPO_ROOT/evidence/staging/$DATE_DIR"
ROLLBACK_DIR="$EVIDENCE_DIR/rollback"
SMOKE_DIR="$EVIDENCE_DIR/smoke"
DUMP_DIR="$EVIDENCE_DIR/dump_logs"

# Inputs (required)
STAGING_CONTEXT="${STAGING_CONTEXT:-}"
STAGING_NAMESPACE="${STAGING_NAMESPACE:-}"
STAGING_BASE_URL="${STAGING_BASE_URL:-}"

# Optional input
ROLLBACK_REVISION="${ROLLBACK_REVISION:-}"  # Empty = rollback to previous (n-1)

# Create evidence directories
mkdir -p "$ROLLBACK_DIR" "$SMOKE_DIR" "$DUMP_DIR"

# Trap errors
DumpLogs() {
  local exit_code=$?
  echo -e "${RED}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"
  echo -e "${RED}[FAILURE] Exit code: $exit_code${NC}"
  echo -e "${RED}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"
  echo "Dumping logs to: $DUMP_DIR"

  if [ -n "$STAGING_CONTEXT" ] && [ -n "$STAGING_NAMESPACE" ]; then
    # K8s describe
    kubectl --context="$STAGING_CONTEXT" describe deployment -n "$STAGING_NAMESPACE" > "$DUMP_DIR/k8s_describe.txt" 2>&1 || true
    kubectl --context="$STAGING_CONTEXT" describe pod -n "$STAGING_NAMESPACE" >> "$DUMP_DIR/k8s_describe.txt" 2>&1 || true

    # K8s events
    kubectl --context="$STAGING_CONTEXT" get events -n "$STAGING_NAMESPACE" --sort-by='.lastTimestamp' > "$DUMP_DIR/k8s_events.txt" 2>&1 || true

    # App logs
    kubectl --context="$STAGING_CONTEXT" logs -l app=dpp-api -n "$STAGING_NAMESPACE" --tail=200 > "$DUMP_DIR/app_logs_tail.txt" 2>&1 || true
  fi

  echo -e "${RED}Logs dumped. Check: $DUMP_DIR${NC}"
  exit "$exit_code"
}

trap DumpLogs ERR

echo -e "${BLUE}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"
echo -e "${BLUE}Rollback Drill${NC}"
echo -e "${BLUE}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"
echo "Date: $(date -u +"%Y-%m-%dT%H:%M:%SZ")"
echo "Evidence: $EVIDENCE_DIR"
echo ""

# Step 1: Validate Inputs
echo -e "${YELLOW}[1/6] Validating inputs...${NC}"

if [ -z "$STAGING_CONTEXT" ]; then
  echo -e "${RED}ERROR: STAGING_CONTEXT is not set${NC}"
  echo "Set: export STAGING_CONTEXT=\"staging-cluster\""
  exit 1
fi

if [ -z "$STAGING_NAMESPACE" ]; then
  echo -e "${RED}ERROR: STAGING_NAMESPACE is not set${NC}"
  echo "Set: export STAGING_NAMESPACE=\"dpp-staging\""
  exit 1
fi

if [ -z "$STAGING_BASE_URL" ]; then
  echo -e "${RED}ERROR: STAGING_BASE_URL is not set${NC}"
  echo "Set: export STAGING_BASE_URL=\"https://staging-api.decisionproof.ai\""
  exit 1
fi

echo "✓ Inputs validated"
echo "  Context: $STAGING_CONTEXT"
echo "  Namespace: $STAGING_NAMESPACE"
echo "  Rollback to: ${ROLLBACK_REVISION:-previous (n-1)}"
echo ""

# Step 2: Preflight Check (Rollout History)
echo -e "${YELLOW}[2/6] Checking rollout history...${NC}"

# API
API_HISTORY=$(kubectl --context="$STAGING_CONTEXT" rollout history deployment/dpp-api -n "$STAGING_NAMESPACE" 2>&1 || echo "NO_DEPLOYMENT")
if echo "$API_HISTORY" | grep -q "NO_DEPLOYMENT"; then
  echo -e "${RED}ERROR: dpp-api deployment not found${NC}"
  exit 1
fi

API_REVISION=$(kubectl --context="$STAGING_CONTEXT" get deployment dpp-api -n "$STAGING_NAMESPACE" -o jsonpath='{.metadata.annotations.deployment\.kubernetes\.io/revision}' 2>/dev/null || echo "0")
if [ "$API_REVISION" -lt 2 ]; then
  echo -e "${RED}ERROR: dpp-api has only 1 revision (no previous to rollback to)${NC}"
  echo "Action: Perform a deployment first to create revision 2"
  exit 1
fi

echo "✓ Rollout history OK"
echo "  dpp-api current revision: $API_REVISION"
echo ""

# Step 3: Capture Pre-Rollback State
echo -e "${YELLOW}[3/6] Capturing pre-rollback state...${NC}"

kubectl --context="$STAGING_CONTEXT" get deploy,po,svc -n "$STAGING_NAMESPACE" -o wide > "$ROLLBACK_DIR/status_before.txt" 2>&1

# Capture current revisions
echo "$API_REVISION" > "$ROLLBACK_DIR/revision_before_api.txt"

if kubectl --context="$STAGING_CONTEXT" get deployment dpp-worker -n "$STAGING_NAMESPACE" &> /dev/null; then
  WORKER_REVISION=$(kubectl --context="$STAGING_CONTEXT" get deployment dpp-worker -n "$STAGING_NAMESPACE" -o jsonpath='{.metadata.annotations.deployment\.kubernetes\.io/revision}')
  echo "$WORKER_REVISION" > "$ROLLBACK_DIR/revision_before_worker.txt"
fi

if kubectl --context="$STAGING_CONTEXT" get deployment dpp-reaper -n "$STAGING_NAMESPACE" &> /dev/null; then
  REAPER_REVISION=$(kubectl --context="$STAGING_CONTEXT" get deployment dpp-reaper -n "$STAGING_NAMESPACE" -o jsonpath='{.metadata.annotations.deployment\.kubernetes\.io/revision}')
  echo "$REAPER_REVISION" > "$ROLLBACK_DIR/revision_before_reaper.txt"
fi

echo "✓ State captured"
echo ""

# Step 4: Execute Rollback
echo -e "${YELLOW}[4/6] Executing rollback...${NC}"

ROLLBACK_START=$(date +%s)

{
  echo "# Rollback commands"
  echo "kubectl --context=$STAGING_CONTEXT rollout undo deployment/dpp-api -n $STAGING_NAMESPACE ${ROLLBACK_REVISION:+--to-revision=$ROLLBACK_REVISION}"
  echo "kubectl --context=$STAGING_CONTEXT rollout undo deployment/dpp-worker -n $STAGING_NAMESPACE ${ROLLBACK_REVISION:+--to-revision=$ROLLBACK_REVISION}"
  echo "kubectl --context=$STAGING_CONTEXT rollout undo deployment/dpp-reaper -n $STAGING_NAMESPACE ${ROLLBACK_REVISION:+--to-revision=$ROLLBACK_REVISION}"
} > "$ROLLBACK_DIR/cmd.txt"

# Rollback API
echo "Rolling back dpp-api..."
if [ -z "$ROLLBACK_REVISION" ]; then
  kubectl --context="$STAGING_CONTEXT" rollout undo deployment/dpp-api -n "$STAGING_NAMESPACE" > "$ROLLBACK_DIR/stdout.log" 2> "$ROLLBACK_DIR/stderr.log"
else
  kubectl --context="$STAGING_CONTEXT" rollout undo deployment/dpp-api -n "$STAGING_NAMESPACE" --to-revision="$ROLLBACK_REVISION" > "$ROLLBACK_DIR/stdout.log" 2> "$ROLLBACK_DIR/stderr.log"
fi

# Wait for API rollback
kubectl --context="$STAGING_CONTEXT" rollout status deployment/dpp-api -n "$STAGING_NAMESPACE" --timeout=5m >> "$ROLLBACK_DIR/stdout.log" 2>> "$ROLLBACK_DIR/stderr.log"

# Rollback Worker (if exists)
if kubectl --context="$STAGING_CONTEXT" get deployment dpp-worker -n "$STAGING_NAMESPACE" &> /dev/null; then
  echo "Rolling back dpp-worker..."
  if [ -z "$ROLLBACK_REVISION" ]; then
    kubectl --context="$STAGING_CONTEXT" rollout undo deployment/dpp-worker -n "$STAGING_NAMESPACE" >> "$ROLLBACK_DIR/stdout.log" 2>> "$ROLLBACK_DIR/stderr.log"
  else
    kubectl --context="$STAGING_CONTEXT" rollout undo deployment/dpp-worker -n "$STAGING_NAMESPACE" --to-revision="$ROLLBACK_REVISION" >> "$ROLLBACK_DIR/stdout.log" 2>> "$ROLLBACK_DIR/stderr.log"
  fi
  kubectl --context="$STAGING_CONTEXT" rollout status deployment/dpp-worker -n "$STAGING_NAMESPACE" --timeout=5m >> "$ROLLBACK_DIR/stdout.log" 2>> "$ROLLBACK_DIR/stderr.log"
fi

# Rollback Reaper (if exists)
if kubectl --context="$STAGING_CONTEXT" get deployment dpp-reaper -n "$STAGING_NAMESPACE" &> /dev/null; then
  echo "Rolling back dpp-reaper..."
  if [ -z "$ROLLBACK_REVISION" ]; then
    kubectl --context="$STAGING_CONTEXT" rollout undo deployment/dpp-reaper -n "$STAGING_NAMESPACE" >> "$ROLLBACK_DIR/stdout.log" 2>> "$ROLLBACK_DIR/stderr.log"
  else
    kubectl --context="$STAGING_CONTEXT" rollout undo deployment/dpp-reaper -n "$STAGING_NAMESPACE" --to-revision="$ROLLBACK_REVISION" >> "$ROLLBACK_DIR/stdout.log" 2>> "$ROLLBACK_DIR/stderr.log"
  fi
  kubectl --context="$STAGING_CONTEXT" rollout status deployment/dpp-reaper -n "$STAGING_NAMESPACE" --timeout=5m >> "$ROLLBACK_DIR/stdout.log" 2>> "$ROLLBACK_DIR/stderr.log"
fi

ROLLBACK_END=$(date +%s)
ROLLBACK_DURATION=$((ROLLBACK_END - ROLLBACK_START))

echo "✓ Rollback complete (${ROLLBACK_DURATION}s)"
echo ""

# Step 5: Verify Rollback
echo -e "${YELLOW}[5/6] Verifying rollback...${NC}"

# Capture post-rollback state
kubectl --context="$STAGING_CONTEXT" get deploy,po,svc -n "$STAGING_NAMESPACE" -o wide > "$ROLLBACK_DIR/status_after.txt" 2>&1

# Capture new revisions
API_REVISION_AFTER=$(kubectl --context="$STAGING_CONTEXT" get deployment dpp-api -n "$STAGING_NAMESPACE" -o jsonpath='{.metadata.annotations.deployment\.kubernetes\.io/revision}')
echo "$API_REVISION_AFTER" > "$ROLLBACK_DIR/revision_after_api.txt"

if kubectl --context="$STAGING_CONTEXT" get deployment dpp-worker -n "$STAGING_NAMESPACE" &> /dev/null; then
  WORKER_REVISION_AFTER=$(kubectl --context="$STAGING_CONTEXT" get deployment dpp-worker -n "$STAGING_NAMESPACE" -o jsonpath='{.metadata.annotations.deployment\.kubernetes\.io/revision}')
  echo "$WORKER_REVISION_AFTER" > "$ROLLBACK_DIR/revision_after_worker.txt"
fi

if kubectl --context="$STAGING_CONTEXT" get deployment dpp-reaper -n "$STAGING_NAMESPACE" &> /dev/null; then
  REAPER_REVISION_AFTER=$(kubectl --context="$STAGING_CONTEXT" get deployment dpp-reaper -n "$STAGING_NAMESPACE" -o jsonpath='{.metadata.annotations.deployment\.kubernetes\.io/revision}')
  echo "$REAPER_REVISION_AFTER" > "$ROLLBACK_DIR/revision_after_reaper.txt"
fi

# Verify revision changed
if [ "$API_REVISION" = "$API_REVISION_AFTER" ]; then
  echo -e "${RED}WARNING: API revision did not change (expected change)${NC}"
else
  echo "✓ API revision changed: $API_REVISION → $API_REVISION_AFTER"
fi

echo "✓ Rollback verified"
echo ""

# Step 6: Re-run Smoke Tests
echo -e "${YELLOW}[6/6] Re-running smoke tests (10 checks)...${NC}"

# Wait a bit for services to stabilize
echo "Waiting 10 seconds for services to stabilize..."
sleep 10

# Smoke test suite (same as staging_dry_run)
SMOKE_RESULTS='{"checks": []}'
CHECKS_PASSED=0
CHECKS_TOTAL=10

run_check() {
  local name="$1"
  local url="$2"
  local expected_status="$3"

  local start=$(date +%s%3N)
  local status=$(curl -s -o /dev/null -w '%{http_code}' -m 10 "$url" 2>/dev/null || echo "000")
  local end=$(date +%s%3N)
  local latency=$((end - start))

  local pass=false
  if [ "$status" = "$expected_status" ]; then
    pass=true
    CHECKS_PASSED=$((CHECKS_PASSED + 1))
  fi

  SMOKE_RESULTS=$(echo "$SMOKE_RESULTS" | jq --arg name "$name" --arg url "$url" --argjson pass "$pass" --arg status "$status" --arg latency "$latency" \
    '.checks += [{"name": $name, "url": $url, "pass": $pass, "http_status": $status, "latency_ms": ($latency | tonumber)}]')

  if [ "$pass" = "true" ]; then
    echo "  ✓ $name ($status, ${latency}ms)"
  else
    echo "  ✗ $name (expected $expected_status, got $status)"
  fi
}

echo "Post-rollback smoke test suite:"
run_check "GET /health" "$STAGING_BASE_URL/health" "200"
run_check "GET /readyz" "$STAGING_BASE_URL/readyz" "200"
run_check "GET /.well-known/openapi.json" "$STAGING_BASE_URL/.well-known/openapi.json" "200"
run_check "GET /llms.txt" "$STAGING_BASE_URL/llms.txt" "200"
run_check "GET /api-docs" "$STAGING_BASE_URL/api-docs" "200"
run_check "GET /redoc" "$STAGING_BASE_URL/redoc" "200"
run_check "GET /metrics" "$STAGING_BASE_URL/metrics" "200"
run_check "GET /pricing/ssot.json" "$STAGING_BASE_URL/pricing/ssot.json" "200"
run_check "GET /docs/quickstart.md" "$STAGING_BASE_URL/docs/quickstart.md" "200"
run_check "GET /v1/runs (unauthenticated)" "$STAGING_BASE_URL/v1/runs" "401"

# Save results
echo "$SMOKE_RESULTS" | jq '.' > "$SMOKE_DIR/results_post_rollback.json"

# HTTP samples
{
  echo "=== Post-Rollback Sample 1: GET /health ==="
  curl -s "$STAGING_BASE_URL/health" | jq '.' 2>/dev/null || echo "(not JSON)"
  echo ""
  echo "=== Post-Rollback Sample 2: GET /readyz ==="
  curl -s "$STAGING_BASE_URL/readyz" | jq '.' 2>/dev/null || echo "(not JSON)"
} > "$SMOKE_DIR/http_samples_post_rollback.log"

echo ""
echo "Post-rollback smoke test results: $CHECKS_PASSED/$CHECKS_TOTAL PASS"

# Check threshold (80%)
if [ $CHECKS_PASSED -lt 8 ]; then
  echo -e "${RED}ERROR: Post-rollback smoke tests failed (< 8/10 PASS)${NC}"
  echo "See: $SMOKE_DIR/results_post_rollback.json"
  exit 1
fi

echo "✓ Post-rollback smoke tests PASSED"
echo ""

# Generate/Update Manifest
echo "Updating manifest..."

COMMIT_SHA=$(git -C "$REPO_ROOT" rev-parse HEAD)
DATE_UTC=$(date -u +"%Y-%m-%dT%H:%M:%SZ")
DATE_KST=$(TZ=Asia/Seoul date +"%Y-%m-%d %H:%M:%S %Z")

# Update existing manifest or create new one
MANIFEST_FILE="$EVIDENCE_DIR/manifest.json"
if [ -f "$MANIFEST_FILE" ]; then
  # Update existing manifest
  jq --arg date_utc "$DATE_UTC" \
     --arg rollback_method "kubectl rollout undo" \
     --argjson rollback_duration "$ROLLBACK_DURATION" \
     --argjson checks_passed "$CHECKS_PASSED" \
     --argjson checks_total "$CHECKS_TOTAL" \
     '.rollback = {"ok": true, "method": $rollback_method, "duration_sec": $rollback_duration} |
      .smoke.post_rollback = {"ok": ($checks_passed == $checks_total), "checks_passed": $checks_passed, "checks_total": $checks_total}' \
     "$MANIFEST_FILE" > "${MANIFEST_FILE}.tmp" && mv "${MANIFEST_FILE}.tmp" "$MANIFEST_FILE"
else
  # Create new manifest (rollback-only)
  cat > "$MANIFEST_FILE" <<EOF
{
  "date_utc": "$DATE_UTC",
  "date_kst": "$DATE_KST",
  "commit_sha": "$COMMIT_SHA",
  "mechanism": "k8s",
  "target": {
    "context": "$STAGING_CONTEXT",
    "namespace": "$STAGING_NAMESPACE",
    "base_url": "$STAGING_BASE_URL"
  },
  "deploy": {
    "ok": null,
    "duration_sec": null
  },
  "smoke": {
    "ok": null,
    "checks_passed": null,
    "checks_total": null,
    "post_rollback": {
      "ok": $([ $CHECKS_PASSED -eq $CHECKS_TOTAL ] && echo "true" || echo "false"),
      "checks_passed": $CHECKS_PASSED,
      "checks_total": $CHECKS_TOTAL
    }
  },
  "rollback": {
    "ok": true,
    "method": "kubectl rollout undo",
    "duration_sec": $ROLLBACK_DURATION
  },
  "artifacts": {
    "evidence_dir": "$EVIDENCE_DIR"
  }
}
EOF
fi

echo -e "${GREEN}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"
echo -e "${GREEN}✅ Rollback Drill COMPLETE${NC}"
echo -e "${GREEN}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"
echo "Evidence: $EVIDENCE_DIR"
echo "Rollback: ${ROLLBACK_DURATION}s"
echo "Post-rollback smoke: $CHECKS_PASSED/$CHECKS_TOTAL PASS"
echo "Manifest: $EVIDENCE_DIR/manifest.json"
