#!/usr/bin/env bash
set -Eeuo pipefail

# ==============================================================================
# Customer Packet Rehearsal
# ==============================================================================
# 목적: 고객 관점 리허설 (15분 체크리스트)
# 실행: ./tools/rehearse_customer_packet.sh
# ==============================================================================

die() { echo "FATAL: $*" >&2; exit 1; }
log() { echo "[$(date '+%Y-%m-%d %H:%M:%S')] $*" >&2; }

DumpLogs() {
  log "Dumping evidence logs..."
  if [ -d "$EVDIR" ]; then
    echo "Evidence directory: $EVDIR"
    find "$EVDIR" -type f -name "*.log" -o -name "*.txt" | head -20 || true
  fi
}

trap 'DumpLogs; die "Script failed at line $LINENO"' ERR

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd "$SCRIPT_DIR/.." && pwd)"
cd "$REPO_ROOT"

DATE_YYYYMMDD_HHMMSS="$(date +%Y%m%d_%H%M%S)"
EVDIR="evidence/pilot_packet_review/${DATE_YYYYMMDD_HHMMSS}"
mkdir -p "$EVDIR"/{preflight,build,unzip,scan,linkcheck}

log "Starting Customer Packet Rehearsal"
log "Evidence Dir: $EVDIR"

# ==============================================================================
# 1. Preflight
# ==============================================================================
log "[1/7] Preflight checks..."

PREFLIGHT_DIR="$EVDIR/preflight"

# Version info
{
  echo "Git SHA: $(git rev-parse HEAD 2>/dev/null || echo 'n/a')"
  echo "Git Short SHA: $(git rev-parse --short HEAD 2>/dev/null || echo 'n/a')"
  echo "Bash: $BASH_VERSION"
  echo "Python: $(python --version 2>&1 || echo 'n/a')"
  command -v unzip >/dev/null 2>&1 && echo "unzip: $(unzip -v 2>&1 | head -1 || echo 'n/a')" || echo "unzip: not found"
  command -v grep >/dev/null 2>&1 && echo "grep: $(grep --version 2>&1 | head -1 || echo 'n/a')" || echo "grep: not found"
} > "$PREFLIGHT_DIR/versions.txt"

# Input params
{
  echo "PACKET_MODE: customer"
  echo "Build Script: tools/build_pilot_kickoff_packet.sh"
  echo "Date: $(date -Iseconds)"
} > "$PREFLIGHT_DIR/inputs.txt"

log "✅ Preflight complete"

# ==============================================================================
# 2. Build customer packet
# ==============================================================================
log "[2/7] Building customer packet..."

BUILD_DIR="$EVDIR/build"
set +e
PACKET_MODE=customer bash tools/build_pilot_kickoff_packet.sh >"$BUILD_DIR/stdout.log" 2>"$BUILD_DIR/stderr.log"
BUILD_RC=$?
set -e
echo "$BUILD_RC" > "$BUILD_DIR/exit_code.txt"

if [ "$BUILD_RC" -ne 0 ]; then
  die "Build failed (exit=$BUILD_RC). See $BUILD_DIR/stderr.log"
fi

log "✅ Build complete"

# ==============================================================================
# 3. Locate ZIP
# ==============================================================================
log "[3/7] Locating customer ZIP..."

DATE_YYYYMMDD=$(date +%Y%m%d)
EXPECTED_ZIP="dist/pilot_kickoff_packet_customer_${DATE_YYYYMMDD}.zip"
ZIP_PATH=""

if [ -f "$EXPECTED_ZIP" ]; then
  ZIP_PATH="$EXPECTED_ZIP"
else
  # Fallback: most recent customer zip
  ZIP_PATH="$(ls -1t dist/pilot_kickoff_packet_customer_*.zip 2>/dev/null | head -1 || true)"
fi

if [ -z "$ZIP_PATH" ] || [ ! -f "$ZIP_PATH" ]; then
  die "Customer ZIP not found (expected: $EXPECTED_ZIP)"
fi

echo "$ZIP_PATH" > "$EVDIR/unzip/zip_path.txt"
log "Found ZIP: $ZIP_PATH"

# ==============================================================================
# 4. ZIP integrity + list + extract
# ==============================================================================
log "[4/7] ZIP verification..."

UNZIP_DIR="$EVDIR/unzip"

# Integrity test
if command -v unzip >/dev/null 2>&1; then
  unzip -t "$ZIP_PATH" > "$UNZIP_DIR/zip_test.txt" 2>&1 || die "ZIP integrity test failed"
  unzip -l "$ZIP_PATH" > "$UNZIP_DIR/zip_list.txt" 2>&1 || die "ZIP listing failed"
else
  # Python fallback
  python - <<'PY' "$ZIP_PATH" "$UNZIP_DIR"
import sys, zipfile, os
zp, udir = sys.argv[1], sys.argv[2]
with zipfile.ZipFile(zp, "r") as z:
    bad = z.testzip()
    if bad:
        raise SystemExit(f"ZIP integrity test failed: {bad}")
    names = z.namelist()
open(os.path.join(udir,"zip_test.txt"),"w").write("OK\n")
open(os.path.join(udir,"zip_list.txt"),"w").write("\n".join(names)+"\n")
PY
fi

# Extract
EXTRACT_DIR="$EVDIR/extracted"
mkdir -p "$EXTRACT_DIR"

if command -v unzip >/dev/null 2>&1; then
  unzip -q "$ZIP_PATH" -d "$EXTRACT_DIR" || die "ZIP extraction failed"
else
  python - <<'PY' "$ZIP_PATH" "$EXTRACT_DIR"
import sys, zipfile
zp, exdir = sys.argv[1], sys.argv[2]
with zipfile.ZipFile(zp, "r") as z:
    z.extractall(exdir)
PY
fi

echo "$EXTRACT_DIR" > "$UNZIP_DIR/extract_dir.txt"
log "✅ ZIP extracted to $EXTRACT_DIR"

# ==============================================================================
# 5. Required files check
# ==============================================================================
log "[5/7] Checking required files..."

REQUIRED_FILES=(
  "pilot/00_README_KICKOFF.md"
  "pilot/01_ONBOARDING_CHECKLIST.md"
  "pilot/02_QUICKSTART_FOR_PILOT.md"
  "pilot/03_SUPPORT_AND_ESCALATION.md"
  "pilot/04_BILLING_AND_REFUND.md"
  "pilot/05_SECURITY_PRIVACY_BASELINE.md"
  "pilot/06_ACCEPTABLE_USE_POLICY.md"
  "pilot/07_AI_DISCLOSURE.md"
  "pilot/08_OFFBOARDING_AND_DATA_RETENTION.md"
  "pilot/09_CHANGELOG_AND_CONTACTS.md"
  "manifest.txt"
)

MISSING_COUNT=0
for rf in "${REQUIRED_FILES[@]}"; do
  if [ ! -f "$EXTRACT_DIR/$rf" ]; then
    echo "MISSING: $rf" | tee -a "$UNZIP_DIR/missing_files.txt"
    MISSING_COUNT=$((MISSING_COUNT + 1))
  fi
done

if [ "$MISSING_COUNT" -gt 0 ]; then
  die "Required files missing: $MISSING_COUNT (see $UNZIP_DIR/missing_files.txt)"
fi

# Check references NOT present in customer mode
if [ -d "$EXTRACT_DIR/references" ]; then
  echo "WARN: references/ found in customer packet (should be excluded)" | tee "$UNZIP_DIR/references_warn.txt"
  log "⚠️  WARNING: references/ should not be in customer packet"
fi

log "✅ All required files present"

# ==============================================================================
# 6. Scan internal content
# ==============================================================================
log "[6/7] Scanning for internal content..."

SCAN_DIR="$EVDIR/scan"
set +e
SCAN_ROOT="$EXTRACT_DIR/pilot" bash tools/scan_internal_content.sh > "$SCAN_DIR/scan_stdout.log" 2>"$SCAN_DIR/scan_stderr.log"
SCAN_RC=$?
set -e
echo "$SCAN_RC" > "$SCAN_DIR/scan_exit_code.txt"

if [ "$SCAN_RC" -ne 0 ]; then
  log "❌ Internal content scan FAILED"
  die "Internal content issues detected (see $SCAN_DIR/)"
fi

# Copy scan evidence
cp -r evidence/scan_internal_content/* "$SCAN_DIR/" 2>/dev/null || true

log "✅ Internal content scan passed"

# ==============================================================================
# 7. Link check (markdown internal links)
# ==============================================================================
log "[7/7] Checking markdown links..."

LINKCHECK_DIR="$EVDIR/linkcheck"

# Extract .md links from key files
MD_LINK_PATTERN='\[.*\]\(([^)]+\.md)\)'
LINK_FILES=(
  "$EXTRACT_DIR/pilot/00_README_KICKOFF.md"
  "$EXTRACT_DIR/pilot/01_ONBOARDING_CHECKLIST.md"
  "$EXTRACT_DIR/pilot/02_QUICKSTART_FOR_PILOT.md"
)

> "$LINKCHECK_DIR/md_links_found.txt"
> "$LINKCHECK_DIR/md_links_missing.txt"

for lf in "${LINK_FILES[@]}"; do
  if [ -f "$lf" ]; then
    grep -oE '\[.*\]\([^)]+\.md\)' "$lf" | grep -oE '\([^)]+\.md\)' | sed 's/[()]//g' >> "$LINKCHECK_DIR/md_links_found.txt" 2>/dev/null || true
  fi
done

# Check if linked files exist
MISSING_LINKS=0
if [ -f "$LINKCHECK_DIR/md_links_found.txt" ]; then
  while IFS= read -r link; do
    # Resolve relative to pilot/
    link_path="$EXTRACT_DIR/pilot/$link"
    if [ ! -f "$link_path" ]; then
      echo "MISSING: $link" | tee -a "$LINKCHECK_DIR/md_links_missing.txt"
      MISSING_LINKS=$((MISSING_LINKS + 1))
    fi
  done < "$LINKCHECK_DIR/md_links_found.txt"
fi

if [ "$MISSING_LINKS" -gt 0 ]; then
  die "Broken markdown links: $MISSING_LINKS (see $LINKCHECK_DIR/md_links_missing.txt)"
fi

log "✅ All markdown links valid"

# ==============================================================================
# 8. Generate 15-minute rehearsal checklist
# ==============================================================================
log "Generating 15-minute rehearsal checklist..."

REHEARSAL_FILE="$EVDIR/rehearsal_checklist.txt"

cat > "$REHEARSAL_FILE" <<'CHECKLIST'
================================================================================
15분 고객 관점 리허설 체크리스트
================================================================================

시작 시간: _____:_____ (기록)
완료 예상: 15분 후

--------------------------------------------------------------------------------
[ ] 1. ZIP 압축 해제 (1분)
    - pilot_kickoff_packet_customer_YYYYMMDD.zip 압축 풀기
    - 폴더 구조 확인: pilot/, manifest.txt

[ ] 2. manifest.txt 확인 (1분)
    - Packet Mode: customer 확인
    - 파일 목록 10개 확인
    - References 없음 확인

[ ] 3. 00_README_KICKOFF.md 읽기 (3분)
    - 파일럿 범위 이해 (STARTER 플랜, Staging 전용)
    - 성공 기준 확인 (10개 시나리오, 99% uptime, p95 < 500ms)
    - 지원 채널 확인

[ ] 4. 01_ONBOARDING_CHECKLIST.md 체크리스트 따라하기 (3분)
    - Phase 1: 계정 설정 (이메일 확인)
    - Phase 2: 네트워크 연결 (curl 테스트)
    - Phase 3: Health Check (GET /health)

[ ] 5. 02_QUICKSTART_FOR_PILOT.md API 호출 (4분)
    - BASE_URL 설정: export BASE_URL=https://staging-api.decisionproof.ai
    - TOKEN 설정: export TOKEN=sk_staging_...
    - /health 호출: curl $BASE_URL/health
    - /readyz 호출: curl $BASE_URL/readyz
    - 인증 테스트: curl -H "Authorization: Bearer $TOKEN" $BASE_URL/v1/runs

[ ] 6. 03_SUPPORT_AND_ESCALATION.md 확인 (1분)
    - 지원 이메일 저장: ghilplip934@gmail.com
    - S0/S1/S2/S3 심각도 정의 이해
    - 응답 목표 시간 확인

[ ] 7. 04_BILLING_AND_REFUND.md 요금제 확인 (1분)
    - STARTER: ₩29,000/월, 1,000 DC 포함
    - Overage: ₩39/DC
    - Rate Limit: 60 RPM

[ ] 8. 보안 및 정책 문서 스캔 (30초)
    - 05_SECURITY_PRIVACY_BASELINE.md
    - 06_ACCEPTABLE_USE_POLICY.md
    - 07_AI_DISCLOSURE.md

[ ] 9. 종료 및 데이터 보관 확인 (30초)
    - 08_OFFBOARDING_AND_DATA_RETENTION.md
    - 데이터 보관 기간: 종료 후 30일

[ ] 10. 변경 로그 및 연락처 확인 (30초)
    - 09_CHANGELOG_AND_CONTACTS.md
    - 최신 버전: v0.4.2.2
    - 변경 공지 규칙 확인

--------------------------------------------------------------------------------
종료 시간: _____:_____ (기록)
소요 시간: _____ 분

체크리스트 완료 여부: [ ] PASS  [ ] FAIL (누락 항목: _____________)

================================================================================
CHECKLIST

cat "$REHEARSAL_FILE"

# ==============================================================================
# Final Summary
# ==============================================================================
FINAL_SUMMARY="$EVDIR/final_summary.txt"

cat > "$FINAL_SUMMARY" <<EOF
================================================================================
Customer Packet Rehearsal - Final Summary
================================================================================

Rehearsal Time: $(date -Iseconds)
Evidence Dir: $EVDIR

================================================================================
Results
================================================================================

✅ Build: PASS
✅ ZIP Integrity: PASS
✅ Required Files: PASS (11 files)
✅ Internal Content Scan: PASS
✅ Markdown Links: PASS
✅ References Check: $([ -d "$EXTRACT_DIR/references" ] && echo "WARN (present)" || echo "PASS (excluded)")

================================================================================
Artifacts
================================================================================

ZIP Path: $ZIP_PATH
Extract Dir: $EXTRACT_DIR
Evidence Dir: $EVDIR
Rehearsal Checklist: $REHEARSAL_FILE

================================================================================
Next Steps
================================================================================

1. 15분 리허설 체크리스트 따라하기 (위 파일 참조)
2. 실제 고객에게 전달 전 최종 검토
3. ZIP + SHA256 체크섬 함께 전달

================================================================================
EOF

cat "$FINAL_SUMMARY"

echo ""
echo "=========================================="
echo "✅ CUSTOMER PACKET REHEARSAL: PASS"
echo "=========================================="
echo "Evidence: $EVDIR"
echo "Rehearsal Checklist: $REHEARSAL_FILE"
echo ""
