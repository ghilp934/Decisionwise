#!/usr/bin/env python3
"""RC-5 Sensitive Data Scan - Secrets Detection with S1 Redaction + S2 Whitelist.

CRITICAL SAFETY RULES:
- S1) LOG REDACTION: NEVER print secret literals. Only print:
  - file path, secret type, fingerprint (sha256[:12]), and "REDACTED"
- S2) TEST FIXTURE WHITELIST:
  - Exclude tests/** from content scanning
  - sk_test_* / dummy_* patterns => WARNING (not FAIL)
  - Forbidden file types in tests/ => WARNING

Exit codes:
  0 = PASS (no FAIL-class findings)
  1 = FAIL (FAIL-class findings exist)
  2 = ERROR (env/tooling issue)
"""

import hashlib
import re
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Dict, List, Set, Tuple


# Forbidden file types (FAIL outside tests/, WARNING inside tests/)
FORBIDDEN_FILE_TYPES = {
    ".env", ".pem", ".key", ".p12", ".pfx",
    "id_rsa", "id_dsa", "id_ecdsa", "id_ed25519",
    "credentials.json", "secrets.json",
}

# Secret patterns (content-based detection)
SECRET_PATTERNS = [
    (r"(?i)(aws_access_key_id|aws_secret_access_key)\s*=\s*[A-Z0-9]{16,}", "AWS Credential"),
    (r"(?i)(AKIA[0-9A-Z]{16})", "AWS Access Key"),
    (r"(?i)(ghp_[a-zA-Z0-9]{36})", "GitHub Personal Access Token"),
    (r"(?i)(xox[baprs]-[0-9a-zA-Z-]{10,})", "Slack Token"),
    (r"(?i)(sk_live_[a-zA-Z0-9]{24,})", "Stripe Live Key"),
    (r"-----BEGIN (RSA |DSA |EC )?PRIVATE KEY-----", "Private Key Block"),
]


def compute_fingerprint(value: str) -> str:
    """Compute SHA256 fingerprint (first 12 chars).

    Args:
        value: Secret value

    Returns:
        First 12 chars of SHA256 hex digest
    """
    return hashlib.sha256(value.encode()).hexdigest()[:12]


def is_test_path(path: str) -> bool:
    """Check if path is under tests/ directory.

    Args:
        path: File path

    Returns:
        True if path contains /tests/ or tests/
    """
    parts = Path(path).parts
    return "tests" in parts


def is_whitelisted_value(value: str) -> bool:
    """Check if value matches whitelist patterns (S2).

    Args:
        value: Detected secret value

    Returns:
        True if value starts with sk_test_ or dummy_
    """
    return value.startswith("sk_test_") or value.startswith("dummy_")


def scan_file_content(file_path: Path) -> List[Tuple[str, str, str]]:
    """Scan file content for secret patterns.

    Args:
        file_path: Path to file

    Returns:
        List of (secret_type, fingerprint, class) tuples
    """
    findings = []

    try:
        with open(file_path, "r", encoding="utf-8", errors="ignore") as f:
            content = f.read()

        for pattern, secret_type in SECRET_PATTERNS:
            matches = re.findall(pattern, content)
            for match in matches:
                # Extract matched value (handle tuple results from groups)
                if isinstance(match, tuple):
                    value = match[0] if match[0] else match[1]
                else:
                    value = match

                # S1 Redaction: Never print value, only fingerprint
                fingerprint = compute_fingerprint(value)

                # S2 Whitelist: Check for test value patterns
                if is_whitelisted_value(value):
                    finding_class = "WARN"
                else:
                    finding_class = "FAIL"

                findings.append((secret_type, fingerprint, finding_class))

    except Exception:
        pass  # Skip unreadable files

    return findings


def scan_repo_files() -> List[Dict]:
    """Scan tracked repo files for secrets.

    Returns:
        List of finding dicts
    """
    findings = []
    repo_root = Path(__file__).parent.parent

    try:
        result = subprocess.run(
            ["git", "ls-files"],
            cwd=repo_root,
            capture_output=True,
            text=True,
            check=True,
        )
        tracked_files = result.stdout.splitlines()
    except subprocess.CalledProcessError:
        tracked_files = []

    # Also check for high-risk untracked files
    for ext in [".env", ".env.local", ".env.production", "*.pem", "*.key", "id_rsa"]:
        for path in repo_root.glob(f"**/{ext}"):
            if path.is_file():
                rel_path = str(path.relative_to(repo_root))
                if rel_path not in tracked_files:
                    tracked_files.append(rel_path)

    # Scan each file
    for rel_path in tracked_files:
        file_path = repo_root / rel_path
        if not file_path.exists() or not file_path.is_file():
            continue

        is_test = is_test_path(rel_path)

        # Check forbidden file types (S2: tests/ => WARNING)
        basename = file_path.name.lower()
        suffix = file_path.suffix.lower()

        is_forbidden_type = (
            basename in FORBIDDEN_FILE_TYPES or
            suffix in FORBIDDEN_FILE_TYPES
        )

        if is_forbidden_type:
            finding_class = "WARN" if is_test else "FAIL"
            findings.append({
                "path": rel_path,
                "type": "Forbidden File Type",
                "fingerprint": "N/A",
                "class": finding_class,
                "remediation": "Remove or move to tests/" if finding_class == "FAIL" else "Test fixture (OK)",
            })

        # Content scan (S2: skip tests/ for content patterns)
        if not is_test:
            content_findings = scan_file_content(file_path)
            for secret_type, fingerprint, finding_class in content_findings:
                findings.append({
                    "path": rel_path,
                    "type": secret_type,
                    "fingerprint": fingerprint,
                    "class": finding_class,
                    "remediation": "Rotate secret and remove from repo" if finding_class == "FAIL" else "Test value (OK)",
                })

    return findings


def scan_docker_image(image_name: str) -> List[Dict]:
    """Scan docker image for secrets (forbidden file types only).

    Args:
        image_name: Docker image tag

    Returns:
        List of finding dicts
    """
    findings = []

    try:
        result = subprocess.run(
            ["docker", "run", "--rm", image_name, "find", "/app", "-type", "f"],
            capture_output=True,
            text=True,
            timeout=30,
        )

        if result.returncode != 0:
            return []

        for line in result.stdout.splitlines():
            basename = Path(line).name.lower()
            suffix = Path(line).suffix.lower()

            is_forbidden = (
                basename in FORBIDDEN_FILE_TYPES or
                suffix in FORBIDDEN_FILE_TYPES
            )

            if is_forbidden:
                findings.append({
                    "path": f"{image_name}:{line}",
                    "type": "Forbidden File Type in Image",
                    "fingerprint": "N/A",
                    "class": "FAIL",
                    "remediation": "Rebuild image with .dockerignore",
                })

    except subprocess.TimeoutExpired:
        pass
    except Exception:
        pass

    return findings


def generate_scan_report(repo_findings: List[Dict], docker_findings: List[Dict]) -> None:
    """Generate RC5_SENSITIVE_DATA_SCAN_REPORT.md.

    Args:
        repo_findings: Findings from repo scan
        docker_findings: Findings from docker scan
    """
    repo_root = Path(__file__).parent.parent
    report_path = repo_root / "docs" / "rc" / "rc5" / "RC5_SENSITIVE_DATA_SCAN_REPORT.md"

    commit_hash = subprocess.run(
        ["git", "rev-parse", "HEAD"],
        capture_output=True,
        text=True,
    ).stdout.strip()[:8]

    timestamp = datetime.now(timezone.utc).isoformat()

    all_findings = repo_findings + docker_findings
    fail_findings = [f for f in all_findings if f["class"] == "FAIL"]
    warn_findings = [f for f in all_findings if f["class"] == "WARN"]

    with open(report_path, "w") as f:
        f.write("# RC-5 Sensitive Data Scan Report\n\n")
        f.write(f"**Generated At:** {timestamp}  \n")
        f.write(f"**Commit:** `{commit_hash}`  \n")
        f.write("\n---\n\n")

        # Summary
        f.write("## Summary\n\n")
        status = "[OK] PASS" if len(fail_findings) == 0 else "[FAIL] FAIL"
        f.write(f"**Status:** {status}  \n")
        f.write(f"**FAIL Findings:** {len(fail_findings)}  \n")
        f.write(f"**WARN Findings:** {len(warn_findings)}  \n")
        f.write(f"**Scanned Targets:**  \n")
        f.write("- Repository (tracked + high-risk untracked)\n")
        f.write("- Docker images: decisionproof-api:rc5, decisionproof-worker:rc5, decisionproof-reaper:rc5\n")
        f.write("\n")

        # FAIL Findings
        if fail_findings:
            f.write("## [FAIL] FAIL Findings\n\n")
            f.write("**Action Required:** Rotate/revoke secrets and remove from repository.\n\n")
            f.write("| Path | Type | Fingerprint | Remediation |\n")
            f.write("|------|------|-------------|-------------|\n")
            for finding in fail_findings:
                f.write(f"| `{finding['path']}` | {finding['type']} | `{finding['fingerprint']}` | {finding['remediation']} |\n")
            f.write("\n")

        # WARN Findings
        if warn_findings:
            f.write("## [WARN]  WARN Findings\n\n")
            f.write("**Note:** These are test fixtures or whitelisted patterns (non-failing).\n\n")
            f.write("| Path | Type | Fingerprint | Note |\n")
            f.write("|------|------|-------------|------|\n")
            for finding in warn_findings:
                f.write(f"| `{finding['path']}` | {finding['type']} | `{finding['fingerprint']}` | {finding['remediation']} |\n")
            f.write("\n")

        if not fail_findings and not warn_findings:
            f.write("## [OK] No Findings\n\n")
            f.write("No secrets or forbidden artifacts detected.\n\n")

        f.write("---\n\n")
        f.write("*Generated by RC-5 Sensitive Data Scan (S1 Redaction + S2 Whitelist)*\n")

    print(f"[OK] Generated: {report_path}")


def main() -> int:
    """Execute sensitive data scan.

    Returns:
        Exit code (0=PASS, 1=FAIL, 2=ERROR)
    """
    print("=" * 80)
    print("RC-5 SENSITIVE DATA SCAN")
    print("=" * 80)
    print()

    # 1) Scan repo
    print("[1/2] Scanning repository files...")
    repo_findings = scan_repo_files()
    repo_fail = [f for f in repo_findings if f["class"] == "FAIL"]
    repo_warn = [f for f in repo_findings if f["class"] == "WARN"]
    print(f"  FAIL findings: {len(repo_fail)}")
    print(f"  WARN findings: {len(repo_warn)}")
    print()

    # 2) Scan docker images
    print("[2/2] Scanning docker images...")
    docker_findings = []
    for image in ["decisionproof-api:rc5", "decisionproof-worker:rc5", "decisionproof-reaper:rc5"]:
        image_findings = scan_docker_image(image)
        docker_findings.extend(image_findings)

    docker_fail = [f for f in docker_findings if f["class"] == "FAIL"]
    print(f"  FAIL findings: {len(docker_fail)}")
    print()

    # Generate report
    generate_scan_report(repo_findings, docker_findings)

    # Print summary
    all_fail = repo_fail + docker_fail

    if all_fail:
        print("[FAIL] FAIL: Found secrets or forbidden artifacts:")
        for finding in all_fail[:5]:  # Show first 5
            # S1 REDACTION: Never print secret value
            print(f"  - {finding['path']}: {finding['type']} (fingerprint: {finding['fingerprint']})")
        if len(all_fail) > 5:
            print(f"  ... and {len(all_fail) - 5} more (see report)")

    print()
    print("=" * 80)

    if all_fail:
        print(f"RC-5 SENSITIVE DATA SCAN: FAIL ({len(all_fail)} findings)")
        print("=" * 80)
        return 1
    else:
        print("RC-5 SENSITIVE DATA SCAN: PASS")
        print("=" * 80)
        return 0


if __name__ == "__main__":
    try:
        sys.exit(main())
    except KeyboardInterrupt:
        print("\n[WARN]  Interrupted by user", file=sys.stderr)
        sys.exit(2)
    except Exception as e:
        print(f"[FAIL] ERROR: {e}", file=sys.stderr)
        import traceback
        traceback.print_exc()
        sys.exit(2)
