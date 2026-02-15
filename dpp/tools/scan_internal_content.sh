#!/usr/bin/env bash
set -Eeuo pipefail

# ==============================================================================
# Internal Content Scanner
# ==============================================================================
# 목적: 고객용 문서에서 placeholder/내부 도메인 탐지
# 실행: SCAN_ROOT=docs/pilot ./tools/scan_internal_content.sh
# ==============================================================================

die() { echo "FATAL: $*" >&2; exit 1; }
log() { echo "[$(date '+%Y-%m-%d %H:%M:%S')] $*" >&2; }

trap 'die "Script failed at line $LINENO"' ERR

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd "$SCRIPT_DIR/.." && pwd)"
cd "$REPO_ROOT"

# 입력 설정
SCAN_ROOT="${SCAN_ROOT:-docs/pilot}"
ALLOWLIST_REGEX="${ALLOWLIST_REGEX:-}"

# Evidence 디렉토리
EVIDENCE_DIR="evidence/scan_internal_content/$(date +%Y%m%d_%H%M%S)"
mkdir -p "$EVIDENCE_DIR"

log "Starting Internal Content Scanner"
log "SCAN_ROOT: $SCAN_ROOT"
log "EVIDENCE_DIR: $EVIDENCE_DIR"

# Scan root 존재 확인
if [ ! -d "$SCAN_ROOT" ]; then
  die "SCAN_ROOT not found: $SCAN_ROOT"
fi

# ------------------------------------------------------------------------------
# 1. Placeholder 패턴 탐지 (FAIL)
# ------------------------------------------------------------------------------
log "Scanning for placeholders..."

PLACEHOLDER_PATTERNS=(
  "TODO"
  "TBD"
  "FIXME"
  "<FILL_ME>"
  "REPLACE_ME"
  "CHANGEME"
  "XXX"
  "TODOCS"
)

PLACEHOLDER_HITS="$EVIDENCE_DIR/placeholders_hits.txt"
> "$PLACEHOLDER_HITS"

for pattern in "${PLACEHOLDER_PATTERNS[@]}"; do
  grep -RInE "$pattern" "$SCAN_ROOT" >> "$PLACEHOLDER_HITS" 2>/dev/null || true
done

PLACEHOLDER_COUNT=$(wc -l < "$PLACEHOLDER_HITS" || echo 0)
log "Placeholder hits: $PLACEHOLDER_COUNT"

# ------------------------------------------------------------------------------
# 2. 내부 도메인/로컬/클러스터 패턴 탐지 (FAIL)
# ------------------------------------------------------------------------------
log "Scanning for internal domains..."

INTERNAL_PATTERNS=(
  "localhost"
  "127\.0\.0\.1"
  "0\.0\.0\.0"
  "\.local"
  "\.internal"
  "\.corp"
  "cluster\.local"
  "svc\.cluster\.local"
  "kubernetes\.default"
)

INTERNAL_HITS="$EVIDENCE_DIR/internal_domain_hits.txt"
> "$INTERNAL_HITS"

for pattern in "${INTERNAL_PATTERNS[@]}"; do
  grep -RInE "$pattern" "$SCAN_ROOT" >> "$INTERNAL_HITS" 2>/dev/null || true
done

INTERNAL_COUNT=$(wc -l < "$INTERNAL_HITS" || echo 0)
log "Internal domain hits: $INTERNAL_COUNT"

# ------------------------------------------------------------------------------
# 3. 경고 패턴 탐지 (WARN)
# ------------------------------------------------------------------------------
log "Scanning for warning patterns..."

WARNING_PATTERNS=(
  "dpp-production"
  "prod-cluster"
  "staging-cluster"
  "kubeconfig"
  "kubectl config use-context"
)

WARNING_HITS="$EVIDENCE_DIR/warnings_hits.txt"
> "$WARNING_HITS"

for pattern in "${WARNING_PATTERNS[@]}"; do
  grep -RInE "$pattern" "$SCAN_ROOT" >> "$WARNING_HITS" 2>/dev/null || true
done

WARNING_COUNT=$(wc -l < "$WARNING_HITS" || echo 0)
log "Warning hits: $WARNING_COUNT"

# ------------------------------------------------------------------------------
# 4. 요약 생성
# ------------------------------------------------------------------------------
SUMMARY_FILE="$EVIDENCE_DIR/summary.txt"

cat > "$SUMMARY_FILE" <<EOF
================================================================================
Internal Content Scan Summary
================================================================================

Scan Time: $(date -Iseconds)
Scan Root: $SCAN_ROOT
Evidence Dir: $EVIDENCE_DIR

================================================================================
Results
================================================================================

Placeholder Hits (FAIL if > 0): $PLACEHOLDER_COUNT
Internal Domain Hits (FAIL if > 0): $INTERNAL_COUNT
Warning Hits (WARN only): $WARNING_COUNT

================================================================================
Details
================================================================================

Placeholder Hits:
$(head -20 "$PLACEHOLDER_HITS" 2>/dev/null || echo "  (none)")

Internal Domain Hits:
$(head -20 "$INTERNAL_HITS" 2>/dev/null || echo "  (none)")

Warning Hits:
$(head -20 "$WARNING_HITS" 2>/dev/null || echo "  (none)")

================================================================================
EOF

cat "$SUMMARY_FILE"

# ------------------------------------------------------------------------------
# 5. PASS/FAIL 판정
# ------------------------------------------------------------------------------
FAIL_COUNT=$((PLACEHOLDER_COUNT + INTERNAL_COUNT))

if [ "$FAIL_COUNT" -gt 0 ]; then
  echo ""
  echo "❌ SCAN FAILED: Found $FAIL_COUNT issues in customer-facing documents"
  echo "   - Placeholders: $PLACEHOLDER_COUNT"
  echo "   - Internal Domains: $INTERNAL_COUNT"
  echo ""
  echo "Evidence: $EVIDENCE_DIR"
  exit 1
fi

if [ "$WARNING_COUNT" -gt 0 ]; then
  echo ""
  echo "⚠️  WARNINGS: Found $WARNING_COUNT potential issues (review recommended)"
  echo "Evidence: $EVIDENCE_DIR"
fi

echo ""
echo "✅ SCAN PASSED: No critical issues found"
echo "Evidence: $EVIDENCE_DIR"
