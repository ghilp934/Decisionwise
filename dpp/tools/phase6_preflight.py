#!/usr/bin/env python3
"""
Phase 6.0 Preflight Runner
===========================
Cross-platform (Python 3.12+). Requires no third-party deps beyond stdlib.

Usage:
    python tools/phase6_preflight.py [--continue-dirty]

Exit codes:
    0  → PASS (all FAIL conditions green; WARNs allowed)
    1  → FAIL (any F1-F6 condition triggered)
"""

from __future__ import annotations

import argparse
import datetime
import hashlib
import json
import os
import platform
import re
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

# Force UTF-8 output on Windows (cp949 can't encode ✓ ⚠ etc.)
if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
if hasattr(sys.stderr, "reconfigure"):
    sys.stderr.reconfigure(encoding="utf-8", errors="replace")

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

REPO_ROOT = Path(__file__).resolve().parent.parent  # dpp/
EVIDENCE_BASE = REPO_ROOT / "evidence" / "phase6_0_preflight"

FORBIDDEN_PATTERNS = [
    # Certs / CA bundles accidentally committed
    r"prod-ca-.*\.(crt|cer|pem)$",
    r"supabase-ca.*\.(crt|cer|pem)$",
    # Blocker files
    r"BLOCKER_.*\.txt$",
    # Env files with actual secrets
    r"ops/scripts/phase6_env\.sh$",
    r"ops/scripts/migration_env\.sh$",
]

# Target directories for sslmode=disable grep (F5)
INFRA_DIRS = ["infra", "k8s"]

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _run(cmd: list[str], *, cwd: Path | None = None, capture: bool = True, timeout: int = 60) -> subprocess.CompletedProcess:
    return subprocess.run(
        cmd,
        cwd=str(cwd or REPO_ROOT),
        capture_output=capture,
        text=True,
        timeout=timeout,
    )


def _write(path: Path, content: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content, encoding="utf-8")


def _append_log(path: Path, line: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a", encoding="utf-8") as f:
        f.write(line + "\n")


# ---------------------------------------------------------------------------
# Evidence scaffolding
# ---------------------------------------------------------------------------


def make_evidence_dir() -> Path:
    ts = datetime.datetime.now(datetime.timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    ev = EVIDENCE_BASE / ts
    for sub in ["00_meta", "01_repo_checks", "02_tooling", "03_tests"]:
        (ev / sub).mkdir(parents=True, exist_ok=True)
    return ev


# ---------------------------------------------------------------------------
# F1 — Dirty check
# ---------------------------------------------------------------------------


def check_f1_dirty(continue_dirty: bool) -> tuple[bool, str]:
    """F1: Uncommitted changes without --continue-dirty flag → FAIL."""
    result = _run(["git", "status", "--porcelain"])
    dirty = bool(result.stdout.strip())
    if dirty and not continue_dirty:
        return False, "F1_DIRTY: working tree has uncommitted changes (use --continue-dirty to proceed)"
    status = "WARN(dirty)" if dirty else "CLEAN"
    return True, f"F1_DIRTY_CHECK: {status}"


# ---------------------------------------------------------------------------
# F2 — Forbidden tracked artifacts
# ---------------------------------------------------------------------------


def check_f2_forbidden(ev: Path) -> tuple[bool, str]:
    """F2: Forbidden files tracked in git → FAIL."""
    result = _run(["git", "ls-files"])
    tracked = result.stdout.splitlines()
    violations = []
    for pattern in FORBIDDEN_PATTERNS:
        rx = re.compile(pattern, re.IGNORECASE)
        for f in tracked:
            if rx.search(f):
                violations.append(f)

    report_lines = [f"Tracked files: {len(tracked)}", ""]
    if violations:
        report_lines.append("VIOLATIONS FOUND:")
        report_lines.extend(f"  {v}" for v in violations)
    else:
        report_lines.append("No forbidden tracked artifacts found.")

    _write(ev / "01_repo_checks" / "tracked_forbidden_artifacts.txt", "\n".join(report_lines))

    if violations:
        return False, f"F2_FORBIDDEN: {len(violations)} forbidden file(s) tracked: {violations}"
    return True, f"F2_FORBIDDEN_CHECK: CLEAN (0 violations in {len(tracked)} tracked files)"


# ---------------------------------------------------------------------------
# F3 — CRLF check
# ---------------------------------------------------------------------------


def check_f3_crlf(ev: Path) -> tuple[bool, str]:
    """F3: CRLF line endings in .py/.sh files → FAIL."""
    result = _run(["git", "ls-files", "--", "*.py", "*.sh"])
    files = [f.strip() for f in result.stdout.splitlines() if f.strip()]

    crlf_files = []
    checked = 0
    for rel in files:
        path = REPO_ROOT / rel
        if not path.is_file():
            continue
        checked += 1
        try:
            raw = path.read_bytes()
            if b"\r\n" in raw:
                crlf_files.append(rel)
        except OSError:
            pass

    report = f"Files checked: {checked}\n"
    if crlf_files:
        report += "CRLF files:\n" + "\n".join(f"  {f}" for f in crlf_files)
    else:
        report += "No CRLF files found."
    _write(ev / "01_repo_checks" / "crlf_scan.txt", report)

    if crlf_files:
        return False, f"F3_CRLF: {len(crlf_files)} file(s) with CRLF: {crlf_files[:3]}..."
    return True, f"F3_CRLF_CHECK: CLEAN ({checked} files checked)"


# ---------------------------------------------------------------------------
# F4 — TLS drift gate
# ---------------------------------------------------------------------------


def check_f4_tls_drift(ev: Path) -> tuple[bool, str]:
    """F4: tls_drift_gate.py exits non-zero → FAIL."""
    gate = REPO_ROOT / "tools" / "security" / "tls_drift_gate.py"
    if not gate.is_file():
        msg = "SKIP: tls_drift_gate.py not found"
        _write(ev / "01_repo_checks" / "tls_drift_gate_report.txt", msg)
        return False, f"F4_TLS_DRIFT: FAIL — gate file missing at {gate}"

    result = _run(
        [sys.executable, str(gate)],
        capture=True,
        timeout=120,
    )
    report = f"Exit code: {result.returncode}\n\nSTDOUT:\n{result.stdout}\n\nSTDERR:\n{result.stderr}"
    _write(ev / "01_repo_checks" / "tls_drift_gate_report.txt", report)

    if result.returncode != 0:
        return False, f"F4_TLS_DRIFT: FAIL (exit {result.returncode}) — see tls_drift_gate_report.txt"
    return True, "F4_TLS_DRIFT: PASS"


# ---------------------------------------------------------------------------
# F5 — sslmode=disable in infra/k8s
# ---------------------------------------------------------------------------


def check_f5_sslmode(ev: Path) -> tuple[bool, str]:
    """F5: sslmode=disable found in infra/ or k8s/ → FAIL."""
    violations: list[str] = []

    for dirn in INFRA_DIRS:
        target = REPO_ROOT / dirn
        if not target.is_dir():
            continue
        for path in target.rglob("*"):
            if not path.is_file():
                continue
            # Skip binary-like extensions
            if path.suffix.lower() in {".png", ".jpg", ".jpeg", ".gif", ".ico", ".woff", ".ttf"}:
                continue
            try:
                text = path.read_text(encoding="utf-8", errors="replace")
            except OSError:
                continue
            if "sslmode=disable" in text:
                rel = str(path.relative_to(REPO_ROOT))
                violations.append(rel)

    report = f"Directories scanned: {', '.join(INFRA_DIRS)}\n"
    if violations:
        report += "sslmode=disable found in:\n" + "\n".join(f"  {v}" for v in violations)
    else:
        report += "No sslmode=disable found."
    _write(ev / "01_repo_checks" / "sslmode_disable_grep.txt", report)

    if violations:
        return False, f"F5_SSLMODE_DISABLE: {len(violations)} file(s): {violations}"
    return True, f"F5_SSLMODE_DISABLE: CLEAN (scanned {', '.join(INFRA_DIRS)})"


# ---------------------------------------------------------------------------
# F6 — Pytest smoke tests (2 critical tests)
# ---------------------------------------------------------------------------


SMOKE_TESTS = [
    "apps/api/tests/test_rc12_tls_drift_gate.py",
    "apps/api/tests/test_rc13_worm_required_guard.py",
]


def check_f6_pytest(ev: Path) -> tuple[bool, str]:
    """F6: Phase 6 smoke pytest tests fail → FAIL."""
    test_dir = ev / "03_tests"
    all_pass = True
    results: list[str] = []

    for test_file in SMOKE_TESTS:
        log_name = Path(test_file).stem + ".log"
        log_path = test_dir / log_name

        result = _run(
            [sys.executable, "-m", "pytest", test_file, "-v", "-o", "addopts=", "--tb=short"],
            capture=True,
            timeout=120,
        )
        combined = f"Exit code: {result.returncode}\n\nSTDOUT:\n{result.stdout}\n\nSTDERR:\n{result.stderr}"
        _write(log_path, combined)

        status = "PASS" if result.returncode == 0 else "FAIL"
        results.append(f"  {test_file}: {status}")
        if result.returncode != 0:
            all_pass = False

    summary = "\n".join(results)
    if all_pass:
        return True, f"F6_PYTEST_SMOKE: PASS\n{summary}"
    return False, f"F6_PYTEST_SMOKE: FAIL\n{summary}"


# ---------------------------------------------------------------------------
# W1 — Required tooling present
# ---------------------------------------------------------------------------


def check_w1_tooling(ev: Path) -> tuple[str, str]:
    """W1: Missing aws/kubectl/helm/terraform → WARN."""
    tools = {
        "python": [sys.executable, "--version"],
        "pip": [sys.executable, "-m", "pip", "--version"],
        "git": ["git", "--version"],
        "openssl": ["openssl", "version"],
        "aws": ["aws", "--version"],
        "kubectl": ["kubectl", "version", "--client", "--short"],
        "helm": ["helm", "version", "--short"],
        "terraform": ["terraform", "version"],
    }

    lines: list[str] = []
    missing: list[str] = []

    for name, cmd in tools.items():
        try:
            r = subprocess.run(cmd, capture_output=True, text=True, timeout=15)
            ver = (r.stdout or r.stderr).strip().split("\n")[0]
            lines.append(f"{name}: {ver}")
        except (FileNotFoundError, subprocess.TimeoutExpired):
            lines.append(f"{name}: NOT FOUND")
            if name in {"aws", "kubectl", "helm", "terraform"}:
                missing.append(name)

    _write(ev / "02_tooling" / "versions.txt", "\n".join(lines))

    if missing:
        return "WARN", f"W1_TOOLING: missing {missing} — cloud/k8s commands unavailable"
    return "OK", "W1_TOOLING: all tools present"


# ---------------------------------------------------------------------------
# W2 — AWS STS caller identity
# ---------------------------------------------------------------------------


def check_w2_aws_sts() -> tuple[str, str]:
    """W2: aws sts get-caller-identity fails → WARN."""
    result = _run(["aws", "sts", "get-caller-identity", "--profile", "dpp-admin", "--output", "json"])
    if result.returncode != 0:
        return "WARN", f"W2_AWS_STS: WARN — {result.stderr.strip()[:200]}"
    try:
        identity = json.loads(result.stdout)
        account = identity.get("Account", "?")
        arn = identity.get("Arn", "?")
        return "OK", f"W2_AWS_STS: OK (Account={account}, Arn={arn})"
    except json.JSONDecodeError:
        return "OK", "W2_AWS_STS: OK (non-JSON response)"


# ---------------------------------------------------------------------------
# W3 — phase6_env.sh present
# ---------------------------------------------------------------------------


def check_w3_env_file() -> tuple[str, str]:
    """W3: ops/scripts/phase6_env.sh missing → WARN."""
    env_file = REPO_ROOT / "ops" / "scripts" / "phase6_env.sh"
    if env_file.is_file():
        return "OK", "W3_ENV_FILE: ops/scripts/phase6_env.sh found"
    return "WARN", "W3_ENV_FILE: WARN — ops/scripts/phase6_env.sh missing (copy template and fill in values)"


# ---------------------------------------------------------------------------
# Meta / repo snapshot
# ---------------------------------------------------------------------------


def collect_meta(ev: Path) -> dict:
    git_sha = _run(["git", "rev-parse", "HEAD"]).stdout.strip()
    git_branch = _run(["git", "rev-parse", "--abbrev-ref", "HEAD"]).stdout.strip()
    dirty_result = _run(["git", "status", "--porcelain"])
    dirty = bool(dirty_result.stdout.strip())

    meta = {
        "timestamp_utc": datetime.datetime.now(datetime.timezone.utc).isoformat(),
        "git_sha": git_sha,
        "git_branch": git_branch,
        "git_dirty": dirty,
        "os": platform.system(),
        "os_version": platform.version(),
        "python_version": sys.version,
        "script": str(Path(__file__).relative_to(REPO_ROOT)),
    }

    _write(ev / "00_meta" / "manifest.json", json.dumps(meta, indent=2))

    # Git status
    _write(ev / "01_repo_checks" / "git_status.txt", dirty_result.stdout)

    # Git diffstat (modified tracked files)
    diff_result = _run(["git", "diff", "--stat", "HEAD"])
    _write(ev / "01_repo_checks" / "git_diffstat.txt", diff_result.stdout or "(no diff vs HEAD)")

    return meta


# ---------------------------------------------------------------------------
# Summary
# ---------------------------------------------------------------------------

# TODO items for 6.1-6.4 (logged in 99_summary.txt)
TODO_ITEMS = """
╔══════════════════════════════════════════════════════════════════╗
║  Phase 6 TODO Items (not yet executed)                         ║
╚══════════════════════════════════════════════════════════════════╝

Phase 6.1 — Secrets Injection + Active Fail-Fast
  □ Add HMAC pepper + KID keys to k8s/secretproviderclass-dpp-secrets.yaml
  □ Add PayPal, Toss, Audit Bucket keys to secretproviderclass
  □ Implement startup_event() preflight: PayPal OAuth token probe
  □ Implement startup_event() preflight: Toss dummy orderId → 401 = auth OK
  □ Implement startup_event() preflight: HMAC pepper roundtrip

Phase 6.2 — WORM Break-glass Alerting (EventBridge Input Transformer)
  □ CloudTrail Trail: dpp-audit-trail with data events on audit bucket
  □ EventBridge Rule: KillSwitchAuditGovernanceBypass
  □ EventBridge Input Transformer: include $.detail.userIdentity.arn,
      $.detail.sourceIPAddress, $.detail.requestParameters.key (who/where/what)
  □ SNS Topic: kill-switch-audit-break-glass-alerts
  □ SNS Email Subscription + confirmed
  □ Test: simulate bypass event → verify email received

Phase 6.3 — Webhook Concurrency Test
  □ 5 simultaneous webhook events with same event_id (idempotency)
  □ Assert exactly 1 DB row committed (UniqueConstraint guard)
  □ Assert 4 duplicates return 200 (idempotent ack, not 500)
  □ Test: test_rc14_webhook_concurrency.py

Phase 6.4 — Cutover Runbook + WORM Evidence Upload
  □ Write ops/runbooks/phase6_cutover.md (go/no-go checklist)
  □ Create evidence tar.gz: tar czf phase6_evidence.tar.gz evidence/
  □ sha256sum phase6_evidence.tar.gz > phase6_evidence.sha256
  □ Upload to S3 WORM audit bucket with ObjectLock

CloudTrail Input Transformer Field Paths (for 6.2 EventBridge):
  • Who:   $.detail.userIdentity.arn
  • Where: $.detail.sourceIPAddress
  • What:  $.detail.requestParameters.key
  • When:  $.detail.eventTime
  • Event: $.detail.eventName
"""


def write_summary(ev: Path, fail_items: list[str], warn_items: list[str], pass_items: list[str]) -> str:
    overall = "FAIL" if fail_items else ("WARN" if warn_items else "PASS")

    lines = [
        "=" * 66,
        "  Phase 6.0 Preflight Summary",
        f"  Result: {overall}",
        f"  Timestamp: {datetime.datetime.now(datetime.timezone.utc).isoformat()}",
        "=" * 66,
        "",
        "PASS items:",
    ]
    for item in pass_items:
        lines.append(f"  ✓ {item}")

    if warn_items:
        lines.append("\nWARN items:")
        for item in warn_items:
            lines.append(f"  ⚠ {item}")

    if fail_items:
        lines.append("\nFAIL items:")
        for item in fail_items:
            lines.append(f"  ✗ {item}")

    lines.append("")
    lines.append(TODO_ITEMS)
    lines.append("")
    lines.append(f"Evidence directory: {ev}")
    lines.append("=" * 66)

    summary_text = "\n".join(lines)
    _write(ev / "99_summary.txt", summary_text)
    return overall


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------


def main() -> int:
    parser = argparse.ArgumentParser(description="Phase 6.0 Preflight Runner")
    parser.add_argument(
        "--continue-dirty",
        action="store_true",
        help="Allow uncommitted changes (records WARN instead of FAIL for dirty state)",
    )
    args = parser.parse_args()

    ev = make_evidence_dir()
    print(f"\n{'='*66}")
    print("  Phase 6.0 Preflight Runner")
    print(f"  Evidence: {ev}")
    print(f"{'='*66}\n")

    # --- Meta ---
    meta = collect_meta(ev)
    print(f"  Branch : {meta['git_branch']}")
    print(f"  SHA    : {meta['git_sha'][:12]}")
    print(f"  Dirty  : {meta['git_dirty']}")
    print(f"  OS     : {meta['os']}")
    print()

    fail_items: list[str] = []
    warn_items: list[str] = []
    pass_items: list[str] = []

    def record(ok: bool | str, msg: str) -> None:
        if ok is True or ok == "OK":
            print(f"  ✓  {msg}")
            pass_items.append(msg)
        elif ok == "WARN":
            print(f"  ⚠  {msg}")
            warn_items.append(msg)
        else:
            print(f"  ✗  {msg}")
            fail_items.append(msg)

    # ---- FAIL checks (F1-F6) ----
    ok, msg = check_f1_dirty(args.continue_dirty)
    record(ok, msg)

    ok, msg = check_f2_forbidden(ev)
    record(ok, msg)

    ok, msg = check_f3_crlf(ev)
    record(ok, msg)

    ok, msg = check_f4_tls_drift(ev)
    record(ok, msg)

    ok, msg = check_f5_sslmode(ev)
    record(ok, msg)

    ok, msg = check_f6_pytest(ev)
    record(ok, msg)

    # ---- WARN checks (W1-W3) ----
    status, msg = check_w1_tooling(ev)
    record(status, msg)

    status, msg = check_w2_aws_sts()
    record(status, msg)

    status, msg = check_w3_env_file()
    record(status, msg)

    # ---- Summary ----
    overall = write_summary(ev, fail_items, warn_items, pass_items)

    print()
    print("=" * 66)
    if overall == "PASS":
        print("  ✅  ALL CHECKS PASSED — Phase 6.0 Preflight: PASS")
    elif overall == "WARN":
        print("  ⚠   WARNINGS ONLY — Phase 6.0 Preflight: PASS (with warnings)")
    else:
        print("  ❌  FAILURES DETECTED — Phase 6.0 Preflight: FAIL")
    print(f"  Evidence: {ev}")
    print(f"  Summary : {ev / '99_summary.txt'}")
    print("=" * 66 + "\n")

    return 0 if overall in {"PASS", "WARN"} else 1


if __name__ == "__main__":
    sys.exit(main())
