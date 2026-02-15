#!/usr/bin/env bash
set -Eeuo pipefail

die() { echo "FATAL: $*" >&2; exit 1; }
log() { echo "[$(date '+%Y-%m-%d %H:%M:%S')] $*" >&2; }

ROOT="$(pwd)"
DATE_YYYYMMDD="$(date +%Y%m%d)"
EVDIR="evidence/pilot_packet/${DATE_YYYYMMDD}"
mkdir -p "${EVDIR}"

# Preflight
[ -f "tools/build_pilot_kickoff_packet.sh" ] || die "Missing tools/build_pilot_kickoff_packet.sh (run from repo root?)"
command -v bash >/dev/null 2>&1 || die "bash not found"
COMMIT_SHA="$(git rev-parse HEAD 2>/dev/null || true)"
echo "${COMMIT_SHA}" > "${EVDIR}/commit_sha.txt"
uname -a > "${EVDIR}/uname.txt" || true

# Capture dist state BEFORE
mkdir -p dist
ls -al dist > "${EVDIR}/dist_before.txt" || true

# Run build (capture logs)
log "Running build_pilot_kickoff_packet.sh ..."
set +e
bash tools/build_pilot_kickoff_packet.sh >"${EVDIR}/build_stdout.log" 2>"${EVDIR}/build_stderr.log"
RC=$?
set -e
echo "${RC}" > "${EVDIR}/build_exit_code.txt"
[ "${RC}" -eq 0 ] || die "build script failed (exit=${RC}). See ${EVDIR}/build_stderr.log"

# Capture dist state AFTER
ls -al dist > "${EVDIR}/dist_after.txt" || true

# Identify zip output
EXPECTED="dist/pilot_kickoff_packet_${DATE_YYYYMMDD}.zip"
ZIP_PATH=""
if [ -f "${EXPECTED}" ]; then
  ZIP_PATH="${EXPECTED}"
else
  # Fallback: take most recent matching zip
  ZIP_PATH="$(ls -1t dist/pilot_kickoff_packet_*.zip 2>/dev/null | head -1 || true)"
fi
[ -n "${ZIP_PATH}" ] || die "No dist/pilot_kickoff_packet_*.zip found after build"
[ -f "${ZIP_PATH}" ] || die "ZIP not found at ${ZIP_PATH}"

echo "${ZIP_PATH}" > "${EVDIR}/zip_path.txt"

# Basic file stats
if command -v stat >/dev/null 2>&1; then
  # macOS stat differs; try both
  (stat "${ZIP_PATH}" || stat -f "%z bytes %N" "${ZIP_PATH}") > "${EVDIR}/zip_stat.txt" 2>/dev/null || true
fi

# SHA256
if command -v sha256sum >/dev/null 2>&1; then
  sha256sum "${ZIP_PATH}" | tee "${EVDIR}/zip_sha256.txt"
elif command -v shasum >/dev/null 2>&1; then
  shasum -a 256 "${ZIP_PATH}" | tee "${EVDIR}/zip_sha256.txt"
elif command -v powershell.exe >/dev/null 2>&1; then
  # Windows PowerShell fallback
  powershell.exe -Command "(Get-FileHash -Algorithm SHA256 '${ZIP_PATH}').Hash" | tee "${EVDIR}/zip_sha256.txt"
else
  die "No sha256sum, shasum, or powershell available"
fi

# Zip integrity test + listing
if command -v unzip >/dev/null 2>&1; then
  unzip -t "${ZIP_PATH}" > "${EVDIR}/zip_test.txt" 2>&1 || die "zip integrity test failed (unzip -t)"
  unzip -l "${ZIP_PATH}" > "${EVDIR}/zip_list.txt" 2>&1 || die "zip listing failed (unzip -l)"
else
  # Python fallback
  python - <<'PY' "${ZIP_PATH}" "${EVDIR}"
import sys, zipfile, os
zp, evdir = sys.argv[1], sys.argv[2]
with zipfile.ZipFile(zp, "r") as z:
    bad = z.testzip()
    if bad:
        raise SystemExit(f"zip integrity test failed, first bad file: {bad}")
    names = z.namelist()
open(os.path.join(evdir,"zip_test.txt"),"w",encoding="utf-8").write("OK\n")
open(os.path.join(evdir,"zip_list.txt"),"w",encoding="utf-8").write("\n".join(names))
PY
fi

# Required files check (inside zip)
# Actual structure from build_pilot_kickoff_packet.sh: pilot/*, references/*, manifest.txt
REQ=(
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
OK_ALL=1
touch "${EVDIR}/required_files_check.txt"
for f in "${REQ[@]}"; do
  if grep -Fq " ${f}" "${EVDIR}/zip_list.txt" || grep -Fq "${f}" "${EVDIR}/zip_list.txt"; then
    echo "OK  ${f}" >> "${EVDIR}/required_files_check.txt"
  else
    echo "MISS ${f}" >> "${EVDIR}/required_files_check.txt"
    OK_ALL=0
  fi
done

# Optional packet validator if exists
if [ -f "tools/pilot_validate_packet.sh" ]; then
  log "Running tools/pilot_validate_packet.sh ..."
  set +e
  bash tools/pilot_validate_packet.sh >"${EVDIR}/validate_stdout.log" 2>"${EVDIR}/validate_stderr.log"
  VRC=$?
  set -e
  echo "${VRC}" > "${EVDIR}/validate_exit_code.txt"
  [ "${VRC}" -eq 0 ] || die "pilot_validate_packet.sh failed (exit=${VRC})"
fi

# Summary output
ZIP_SIZE="$( (wc -c < "${ZIP_PATH}") 2>/dev/null || echo "n/a" )"
SHA_LINE="$(head -1 "${EVDIR}/zip_sha256.txt" 2>/dev/null || true)"
echo "================================================"
echo "✅ PILOT PACKET LOCAL BUILD + VERIFY: PASS"
echo "COMMIT_SHA: ${COMMIT_SHA}"
echo "ZIP_PATH:   ${ZIP_PATH}"
echo "ZIP_SIZE:   ${ZIP_SIZE} bytes"
echo "ZIP_SHA256: ${SHA_LINE}"
echo "EVIDENCE:   ${EVDIR}"
echo "REQ_FILES:  $([ "${OK_ALL}" -eq 1 ] && echo PASS || echo FAIL)"
echo "ZIP_LIST_TOP(30):"
head -30 "${EVDIR}/zip_list.txt" || true
echo "================================================"

[ "${OK_ALL}" -eq 1 ] || die "Required files missing inside zip. See ${EVDIR}/required_files_check.txt"
