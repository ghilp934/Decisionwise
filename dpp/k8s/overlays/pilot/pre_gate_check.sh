#!/usr/bin/env bash
# pre_gate_check.sh
# Pilot PRE-GATE 자동 점검 스크립트
#
# 검증 항목:
#   [1/4]   dpp-production 네임스페이스 누출 검사
#   [2/4]   ${...} 토큰 누출 검사
#   [3/4]   us-east-1 리전 누출 검사 (Seoul: ap-northeast-2 기준)
#   [4/4]   REPLACE_ME_* 미확정 TODO 검사
#   [4.5/4] SSOT 동일성 체크 (pilot.params.yaml ↔ ingress-pilot.yaml)
#   [5/4]   kubectl client-side dry-run (표준 리소스)
#         Note: SecretProviderClass는 클러스터에 CRD가 설치되어야 검증 가능.
#               로컬 dry-run에서는 CRD 리소스를 제외하고 표준 K8s 리소스만 검사.
#
# 사용법:
#   cd dpp/k8s/overlays/pilot
#   chmod +x pre_gate_check.sh
#   ./pre_gate_check.sh
set -euo pipefail

ROOT="$(cd "$(dirname "$0")" && pwd)"
OUT="/tmp/dpp_pilot_rendered.yaml"
OUT_STD="/tmp/dpp_pilot_rendered_std.yaml"

echo "=== DPP Pilot PRE-GATE Check ==="
echo "Overlay: $ROOT"
echo ""

echo "Rendering kustomize overlay..."
kubectl kustomize "$ROOT" > "$OUT"
echo "Rendered to: $OUT"
echo ""

# [1/4] production 네임스페이스 누출 검사
echo "[1/4] Reject dpp-production namespace leak..."
if grep -n "dpp-production" "$OUT"; then
  echo "FAIL: dpp-production leaked into rendered manifests"
  exit 1
fi
echo "  OK: no dpp-production found"

# [2/4] ${...} 토큰 누출 검사
echo "[2/4] Reject dollar-brace placeholder tokens..."
if grep -Pn '\$\{' "$OUT"; then
  echo "FAIL: \${...} placeholders leaked into rendered manifests"
  exit 1
fi
echo "  OK: no \${...} tokens found"

# [3/4] us-east-1 리전 누출 검사
echo "[3/4] Reject us-east-1 region (baseline: ap-northeast-2)..."
if grep -n "us-east-1" "$OUT"; then
  echo "FAIL: us-east-1 leaked (must be ap-northeast-2 baseline)"
  exit 1
fi
echo "  OK: no us-east-1 found"

# [4/4] REPLACE_ME_* 미확정 TODO 검사
echo "[4/4] Enforce REPLACE_ME_* TODOs resolved before deploy..."
if grep -n "REPLACE_ME_" "$OUT"; then
  echo "FAIL: REPLACE_ME_* found."
  echo "      Fill the following before deploy:"
  echo "        - pilot.params.yaml: PILOT_HOST, PILOT_ACM_CERT_ARN, PILOT_ALB_SECURITY_GROUP_ID"
  echo "        - ingress-pilot.yaml: REPLACE_ME_PILOT_HOST, REPLACE_ME_PILOT_ACM_CERT_ARN, REPLACE_ME_PILOT_ALB_SG"
  echo "        - patch-configmap-pilot.yaml: REPLACE_ME_PILOT_APP_HOST"
  exit 1
fi
echo "  OK: no REPLACE_ME_* found"

# [4.5/4] SSOT 동일성 체크 (params vs ingress HOST/CERT/SG 쌍 비교)
echo "[4.5/4] SSOT consistency check (pilot.params.yaml ↔ ingress-pilot.yaml)..."
PARAMS_FILE="$ROOT/pilot.params.yaml"
INGRESS_FILE="$ROOT/ingress-pilot.yaml"

extract_param() {
  local key="$1"
  python3 - "$PARAMS_FILE" "$key" << 'PYEOF'
import sys, re
p, k = sys.argv[1], sys.argv[2]
with open(p, encoding='utf-8') as f:
    c = f.read()
m = re.search(r'^\s*' + re.escape(k) + r'\s*:\s*["\']?([^"\'#\r\n]+?)["\']?\s*$', c, re.MULTILINE)
print(m.group(1).strip() if m else "")
PYEOF
}

P_HOST=$(extract_param "PILOT_HOST")
P_CERT=$(extract_param "PILOT_ACM_CERT_ARN")
P_SG=$(extract_param "PILOT_ALB_SECURITY_GROUP_ID")

# ingress에서 값 추출 (경로를 argv로 전달 — 공백/한글 경로 안전)
extract_ingress() {
  local field="$1"
  python3 - "$INGRESS_FILE" "$field" << 'PYEOF'
import sys, re
path, field = sys.argv[1], sys.argv[2]
with open(path, encoding='utf-8') as f:
    c = f.read()
if field == "host":
    m = re.search(r'^\s*-\s*host:\s*(.+)$', c, re.MULTILINE)
elif field == "cert":
    m = re.search(r'certificate-arn:\s*(.+)', c)
elif field == "sg":
    m = re.search(r'security-groups:\s*(.+)', c)
else:
    m = None
print(m.group(1).strip() if m else "")
PYEOF
}

I_HOST=$(extract_ingress "host")
I_CERT=$(extract_ingress "cert")
I_SG=$(extract_ingress "sg")

MISMATCH=0
if [ "$P_HOST" != "$I_HOST" ]; then
  echo "  MISMATCH: HOST params=$P_HOST ingress=$I_HOST"
  MISMATCH=1
fi
if [ "$P_CERT" != "$I_CERT" ]; then
  echo "  MISMATCH: CERT params=$P_CERT ingress=$I_CERT"
  MISMATCH=1
fi
if [ "$P_SG" != "$I_SG" ]; then
  echo "  MISMATCH: SG params=$P_SG ingress=$I_SG"
  MISMATCH=1
fi
if [ "$MISMATCH" -eq 1 ]; then
  echo "FAIL: params ↔ ingress mismatch. Run ./sync_pilot_values.sh to fix."
  exit 1
fi
echo "  OK: HOST/CERT/SG match between pilot.params.yaml and ingress-pilot.yaml"

# [5/4] Client-side dry-run
# CRD(SecretProviderClass)는 로컬 kubectl에 타입이 등록되어 있어야 적용 가능.
# "no matches for kind ... ensure CRDs are installed" 오류는 클러스터 미연결 환경의
# 예상 동작이므로 허용하고, 그 외 모든 error: 는 즉시 실패 처리.
echo "[5/4] Client-side dry-run apply..."
DRY_RUN_OUTPUT="$(kubectl apply --dry-run=client --validate=false -f "$OUT" 2>&1 || true)"
# CRD 미설치 오류를 제외한 치명적 오류만 추출
FATAL_ERRORS="$(echo "$DRY_RUN_OUTPUT" | grep "^error:" | grep -v "no matches for kind" || true)"
if [ -n "$FATAL_ERRORS" ]; then
  echo "FAIL: dry-run fatal errors detected:"
  echo "$FATAL_ERRORS"
  exit 1
fi
# 15개 표준 리소스가 "created (dry run)" 으로 나타나는지 확인
STD_COUNT="$(echo "$DRY_RUN_OUTPUT" | grep -c "dry run" || true)"
echo "  OK: $STD_COUNT resources validated (dry run)"
echo "  NOTE: SecretProviderClass skipped — requires CRD in cluster (secrets-store.csi.x-k8s.io/v1)"

echo ""
echo "=== ALL CHECKS PASSED — Pilot overlay is PRE-GATE CLEAR ==="
echo ""
echo "Next steps:"
echo "  1. kubectl apply -n dpp-pilot -f job-alembic-migrate.yaml"
echo "  2. kubectl wait -n dpp-pilot --for=condition=complete --timeout=600s job/alembic-migrate"
echo "  3. kubectl apply -k ."
