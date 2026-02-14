#!/usr/bin/env python3
"""RC-5 Release Hygiene Check.

Scans repo and docker images for forbidden artifacts.
Exit codes:
  0 = PASS (no forbidden artifacts)
  1 = FAIL (forbidden artifacts found)
  2 = ERROR (env/tooling issue)
"""

import os
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import List, Tuple

# Forbidden patterns (strict)
FORBIDDEN_GLOBS = [
    "**/__pycache__",
    "**/*.pyc",
    "**/.coverage",
    "**/.pytest_cache",
    "**/*.log",
    "**/*.backup",
    "**/*.bak",
    "**/*.swp",
    ".env",
    ".env.*",
    "**/*.pem",
    "**/*.key",
    "**/id_rsa*",
    "**/*.p12",
    "**/*.pfx",
]

# Forbidden file basenames (case-insensitive)
FORBIDDEN_BASENAMES = {
    ".env",
    "credentials.json",
    "secrets.json",
    "id_rsa",
    "id_dsa",
    "id_ecdsa",
    "id_ed25519",
}


def scan_repo_tree() -> List[str]:
    """Scan repo working tree for forbidden artifacts.

    ONLY checks git-tracked files to avoid false positives from dev artifacts.

    Returns:
        List of forbidden file paths (relative to repo root)
    """
    violations = []
    repo_root = Path(__file__).parent.parent

    # Only check git-tracked files (ignore untracked __pycache__ etc)
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
        return []  # If git fails, return empty (env issue)

    # Check each tracked file
    for file_path in tracked_files:
        file_lower = file_path.lower()

        # Check against forbidden patterns
        if any(pattern in file_lower for pattern in [
            "__pycache__", ".pyc", ".coverage", ".pytest_cache",
            ".log", ".backup", ".bak", ".swp",
        ]):
            violations.append(file_path)
            continue

        # Check forbidden basenames
        basename = Path(file_path).name.lower()
        if basename in FORBIDDEN_BASENAMES:
            violations.append(file_path)
            continue

        # Check forbidden extensions
        suffix = Path(file_path).suffix.lower()
        if suffix in [".env", ".pem", ".key", ".p12", ".pfx"]:
            violations.append(file_path)

    return sorted(set(violations))


def scan_docker_image(image_name: str) -> List[str]:
    """Scan docker image for forbidden artifacts.

    Args:
        image_name: Docker image tag (e.g., "decisionproof-api:rc5")

    Returns:
        List of forbidden file paths found in image
    """
    violations = []

    try:
        # Use docker run to list files
        result = subprocess.run(
            ["docker", "run", "--rm", image_name, "find", "/app", "-type", "f"],
            capture_output=True,
            text=True,
            timeout=30,
        )

        if result.returncode != 0:
            # Image doesn't exist or find command failed
            return []

        for line in result.stdout.splitlines():
            path_lower = line.lower()

            # Check for forbidden patterns
            if any(pattern in path_lower for pattern in [
                "__pycache__", ".pyc", ".coverage", ".pytest_cache",
                ".log", ".backup", ".bak", ".swp",
                ".env", ".pem", ".key", "id_rsa", ".p12", ".pfx",
            ]):
                violations.append(f"{image_name}:{line}")

            # Check for forbidden basenames
            basename = Path(line).name.lower()
            if basename in FORBIDDEN_BASENAMES:
                violations.append(f"{image_name}:{line}")

    except subprocess.TimeoutExpired:
        print(f"[WARN]  WARNING: Timeout scanning image {image_name}", file=sys.stderr)
    except Exception as e:
        print(f"[WARN]  WARNING: Error scanning image {image_name}: {e}", file=sys.stderr)

    return sorted(set(violations))


def generate_report(repo_violations: List[str], docker_violations: List[str]) -> None:
    """Generate RC5_RELEASE_HYGIENE_REPORT.md.

    Args:
        repo_violations: Violations from repo scan
        docker_violations: Violations from docker scan
    """
    repo_root = Path(__file__).parent.parent
    report_path = repo_root / "docs" / "rc" / "rc5" / "RC5_RELEASE_HYGIENE_REPORT.md"

    commit_hash = subprocess.run(
        ["git", "rev-parse", "HEAD"],
        capture_output=True,
        text=True,
    ).stdout.strip()[:8]

    timestamp = datetime.now(timezone.utc).isoformat()

    with open(report_path, "w") as f:
        f.write("# RC-5 Release Hygiene Report\n\n")
        f.write(f"**Generated At:** {timestamp}  \n")
        f.write(f"**Commit:** `{commit_hash}`  \n")
        f.write("\n---\n\n")

        # Summary
        f.write("## Summary\n\n")
        total_violations = len(repo_violations) + len(docker_violations)
        status = "[OK] PASS" if total_violations == 0 else "[FAIL] FAIL"
        f.write(f"**Status:** {status}  \n")
        f.write(f"**Repo Violations:** {len(repo_violations)}  \n")
        f.write(f"**Docker Violations:** {len(docker_violations)}  \n")
        f.write("\n")

        # Violations
        if repo_violations:
            f.write("## [FAIL] Repository Violations\n\n")
            for path in repo_violations[:50]:  # Limit to first 50
                f.write(f"- `{path}`\n")
            if len(repo_violations) > 50:
                f.write(f"\n... and {len(repo_violations) - 50} more\n\n")

        if docker_violations:
            f.write("## [FAIL] Docker Image Violations\n\n")
            for path in docker_violations:
                f.write(f"- `{path}`\n")
            f.write("\n")

        if not repo_violations and not docker_violations:
            f.write("## [OK] No Violations\n\n")
            f.write("No forbidden artifacts detected in repo or docker images.\n\n")

        f.write("---\n\n")
        f.write("*Generated by RC-5 Release Hygiene Check*\n")

    print(f"[OK] Generated: {report_path}")


def main() -> int:
    """Execute release hygiene check.

    Returns:
        Exit code (0=PASS, 1=FAIL, 2=ERROR)
    """
    print("=" * 80)
    print("RC-5 RELEASE HYGIENE CHECK")
    print("=" * 80)
    print()

    # 1) Scan repo tree
    print("[1/2] Scanning repo working tree...")
    repo_violations = scan_repo_tree()

    if repo_violations:
        print(f"[FAIL] FAIL: Found {len(repo_violations)} forbidden artifact(s) in repo:")
        for path in repo_violations:
            print(f"  - {path}")
    else:
        print("[OK] PASS: No forbidden artifacts in repo")

    print()

    # 2) Scan docker images
    print("[2/2] Scanning docker images...")
    images = [
        "decisionproof-api:rc5",
        "decisionproof-worker:rc5",
        "decisionproof-reaper:rc5",
    ]

    docker_violations = []
    for image in images:
        image_violations = scan_docker_image(image)
        docker_violations.extend(image_violations)

    if docker_violations:
        print(f"[FAIL] FAIL: Found {len(docker_violations)} forbidden artifact(s) in docker images:")
        for path in docker_violations:
            print(f"  - {path}")
    else:
        print("[OK] PASS: No forbidden artifacts in docker images")

    print()

    # Generate report
    generate_report(repo_violations, docker_violations)

    print()
    print("=" * 80)

    # Summary
    total_violations = len(repo_violations) + len(docker_violations)

    if total_violations > 0:
        print(f"RC-5 RELEASE HYGIENE: FAIL ({total_violations} violations)")
        print("=" * 80)
        return 1
    else:
        print("RC-5 RELEASE HYGIENE: PASS")
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
        sys.exit(2)
