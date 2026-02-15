#!/usr/bin/env bash
set -Eeuo pipefail

# ==============================================================================
# Paid Pilot Kickoff Packet Builder
# ==============================================================================
# 목적: docs/pilot/*.md + references/ → dist/pilot_kickoff_packet_{MODE}_YYYYMMDD.zip
# 산출물: dist/pilot_kickoff_packet_customer_YYYYMMDD.zip (기본)
#         dist/pilot_kickoff_packet_internal_YYYYMMDD.zip (PACKET_MODE=internal)
# 실행: PACKET_MODE=customer ./tools/build_pilot_kickoff_packet.sh (기본)
#       PACKET_MODE=internal ./tools/build_pilot_kickoff_packet.sh
# ==============================================================================

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd "$SCRIPT_DIR/.." && pwd)"
cd "$REPO_ROOT"

# PACKET_MODE 설정 (customer | internal)
PACKET_MODE="${PACKET_MODE:-customer}"

if [[ "$PACKET_MODE" != "customer" && "$PACKET_MODE" != "internal" ]]; then
  echo "ERROR: PACKET_MODE must be 'customer' or 'internal' (got: $PACKET_MODE)"
  exit 1
fi

DATE_STAMP=$(date +%Y%m%d)
DIST_DIR="dist"
BUILD_DIR="$DIST_DIR/pilot_kickoff_build_${PACKET_MODE}"
ZIP_NAME="pilot_kickoff_packet_${PACKET_MODE}_${DATE_STAMP}.zip"
ZIP_PATH="$DIST_DIR/$ZIP_NAME"

INCLUDE_REFERENCES="false"
if [[ "$PACKET_MODE" == "internal" ]]; then
  INCLUDE_REFERENCES="true"
fi

echo "=========================================="
echo "Paid Pilot Kickoff Packet Builder"
echo "=========================================="
echo "날짜: $(date)"
echo "Git SHA: $(git rev-parse --short HEAD)"
echo "Packet Mode: $PACKET_MODE"
echo "Include References: $INCLUDE_REFERENCES"
echo ""

# ------------------------------------------------------------------------------
# 1. 사전 점검
# ------------------------------------------------------------------------------
echo "[1/5] 사전 점검..."

if [ ! -d "docs/pilot" ]; then
  echo "ERROR: docs/pilot/ 디렉토리가 없습니다."
  exit 1
fi

PILOT_FILES=(
  "docs/pilot/00_README_KICKOFF.md"
  "docs/pilot/01_ONBOARDING_CHECKLIST.md"
  "docs/pilot/02_QUICKSTART_FOR_PILOT.md"
  "docs/pilot/03_SUPPORT_AND_ESCALATION.md"
  "docs/pilot/04_BILLING_AND_REFUND.md"
  "docs/pilot/05_SECURITY_PRIVACY_BASELINE.md"
  "docs/pilot/06_ACCEPTABLE_USE_POLICY.md"
  "docs/pilot/07_AI_DISCLOSURE.md"
  "docs/pilot/08_OFFBOARDING_AND_DATA_RETENTION.md"
  "docs/pilot/09_CHANGELOG_AND_CONTACTS.md"
)

for f in "${PILOT_FILES[@]}"; do
  if [ ! -f "$f" ]; then
    echo "ERROR: 필수 파일 누락 - $f"
    exit 1
  fi
done

echo "✅ 10개 Pilot 문서 확인 완료"

# ------------------------------------------------------------------------------
# 2. 빌드 디렉토리 초기화
# ------------------------------------------------------------------------------
echo "[2/5] 빌드 디렉토리 초기화..."

rm -rf "$BUILD_DIR"
mkdir -p "$BUILD_DIR/pilot"

if [[ "$INCLUDE_REFERENCES" == "true" ]]; then
  mkdir -p "$BUILD_DIR/references"
fi

echo "✅ $BUILD_DIR 준비 완료"

# ------------------------------------------------------------------------------
# 3. 파일 복사
# ------------------------------------------------------------------------------
echo "[3/5] 파일 복사 중..."

# Pilot 문서 복사
for f in "${PILOT_FILES[@]}"; do
  cp "$f" "$BUILD_DIR/pilot/"
done
echo "  ✅ 10개 Pilot 문서 복사 완료"

# References 복사 (internal 모드일 때만)
if [[ "$INCLUDE_REFERENCES" == "true" ]]; then
  cp "docs/RC_MASTER_CHECKLIST.md" "$BUILD_DIR/references/"
  echo "  ✅ RC_MASTER_CHECKLIST.md 복사 완료"

  if [ -f "ops/runbooks/staging_dry_run.md" ]; then
    cp "ops/runbooks/staging_dry_run.md" "$BUILD_DIR/references/"
    echo "  ✅ staging_dry_run.md 복사 완료"
  fi

  if [ -f "ops/runbooks/rollback_drill.md" ]; then
    cp "ops/runbooks/rollback_drill.md" "$BUILD_DIR/references/"
    echo "  ✅ rollback_drill.md 복사 완료"
  fi
else
  echo "  ℹ️  References 제외 (customer 모드)"
fi

# ------------------------------------------------------------------------------
# 4. Manifest 생성
# ------------------------------------------------------------------------------
echo "[4/5] Manifest 생성 중..."

MANIFEST_PATH="$BUILD_DIR/manifest.txt"
cat > "$MANIFEST_PATH" <<EOF
================================================================================
Decisionproof API - Paid Pilot Kickoff Packet
================================================================================

생성 일시: $(date -Iseconds)
Git SHA: $(git rev-parse HEAD)
Git Short SHA: $(git rev-parse --short HEAD)
Git Branch: $(git rev-parse --abbrev-ref HEAD)
API Version: v0.4.2.2
Packet Version: 2026-02-15
Packet Mode: $PACKET_MODE
Include References: $INCLUDE_REFERENCES

================================================================================
파일 목록
================================================================================

[Pilot 문서 - 10개]
EOF

for f in "${PILOT_FILES[@]}"; do
  filename=$(basename "$f")
  echo "  - pilot/$filename" >> "$MANIFEST_PATH"
done

if [[ "$INCLUDE_REFERENCES" == "true" ]]; then
  cat >> "$MANIFEST_PATH" <<EOF

[참조 문서]
  - references/RC_MASTER_CHECKLIST.md
EOF

  if [ -f "ops/runbooks/staging_dry_run.md" ]; then
    echo "  - references/staging_dry_run.md" >> "$MANIFEST_PATH"
  fi

  if [ -f "ops/runbooks/rollback_drill.md" ]; then
    echo "  - references/rollback_drill.md" >> "$MANIFEST_PATH"
  fi
fi

cat >> "$MANIFEST_PATH" <<EOF

================================================================================
사용 방법
================================================================================

1. pilot/00_README_KICKOFF.md부터 순서대로 읽기
2. 온보딩: 01_ONBOARDING_CHECKLIST.md 따라 진행
3. API 호출: 02_QUICKSTART_FOR_PILOT.md 참고
4. 문제 발생 시: 03_SUPPORT_AND_ESCALATION.md 참조

================================================================================
연락처
================================================================================

파일럿 지원: pilot-support@decisionproof.ai
기술 지원: tech-support@decisionproof.ai
Slack: #dpp-pilot-support
운영 시간: 월~금 09:00~18:00 (KST)

================================================================================
EOF

echo "✅ manifest.txt 생성 완료"

# ------------------------------------------------------------------------------
# 5. ZIP 생성
# ------------------------------------------------------------------------------
echo "[5/5] ZIP 패키징 중..."

mkdir -p "$DIST_DIR"
rm -f "$ZIP_PATH"

# Use Python zipfile (cross-platform compatible)
python - <<'PYZIP' "$BUILD_DIR" "$ZIP_PATH"
import sys, zipfile, os
build_dir = sys.argv[1]
zip_path = sys.argv[2]
with zipfile.ZipFile(zip_path, 'w', zipfile.ZIP_DEFLATED) as zf:
    for root, dirs, files in os.walk(build_dir):
        for file in files:
            file_path = os.path.join(root, file)
            arcname = os.path.relpath(file_path, build_dir)
            zf.write(file_path, arcname)
print(f"Created {zip_path}")
PYZIP

echo "✅ ZIP 생성 완료"

# ------------------------------------------------------------------------------
# 완료 보고
# ------------------------------------------------------------------------------
echo ""
echo "=========================================="
echo "✅ 패키징 완료"
echo "=========================================="
echo "산출물: $ZIP_PATH"

# File size (cross-platform)
if [ -f "$ZIP_PATH" ]; then
  ZIP_SIZE=$(python -c "import os; print(os.path.getsize('$ZIP_PATH'))")
  echo "크기: $ZIP_SIZE bytes ($(python -c "print(f'{$ZIP_SIZE/1024:.1f}') if $ZIP_SIZE >= 1024 else print('$ZIP_SIZE')") KB)"

  # File count using Python
  FILE_COUNT=$(python -c "import zipfile; z=zipfile.ZipFile('$ZIP_PATH'); print(len(z.namelist()))")
  echo "파일 수: $FILE_COUNT"
fi
echo ""
echo "검증:"
echo "  unzip -l $ZIP_PATH"
echo ""
echo "추출:"
echo "  unzip $ZIP_PATH -d extracted/"
echo ""
echo "=========================================="
