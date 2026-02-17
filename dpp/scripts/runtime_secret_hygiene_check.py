#!/usr/bin/env python3
"""
Runtime Secret Hygiene Checker.

런타임 설정 파일에서 Supabase API Keys 등 금지된 secrets 검출.

Usage:
    python scripts/runtime_secret_hygiene_check.py
    python scripts/runtime_secret_hygiene_check.py --relaxed

Exit Codes:
    0: PASS (no forbidden secrets detected)
    1: FAIL (forbidden secrets detected)

Forbidden Patterns:
    - SUPABASE_SERVICE_ROLE_KEY=*
    - SUPABASE_ANON_KEY=*
    - URLs containing "supabase.co" in env var values
    - "service_role" in env var values

Scan Paths:
    - dpp/k8s/**/*.yaml
    - dpp/.env*
    - dpp/apps/**/.env*

Relaxed Mode (--relaxed):
    Report violations as warnings only, exit 0 (for CI non-blocking checks).
"""

import argparse
import re
import sys
from pathlib import Path


# Forbidden patterns (case-insensitive)
FORBIDDEN_PATTERNS = [
    (r"SUPABASE_SERVICE_ROLE_KEY\s*[=:]", "SUPABASE_SERVICE_ROLE_KEY"),
    (r"SUPABASE_ANON_KEY\s*[=:]", "SUPABASE_ANON_KEY"),
    (r"[=:]\s*['\"]?https?://[^'\"\s]*supabase\.co", "supabase.co URL"),
    (r"[=:]\s*['\"]?[^'\"\s]*service_role[^'\"\s]*['\"]?", "service_role token"),
]


def scan_file(file_path: Path) -> list[tuple[int, str, str]]:
    """
    Scan a single file for forbidden patterns.

    Args:
        file_path: Path to file to scan.

    Returns:
        List of (line_number, pattern_name, line_content) tuples.
    """
    violations = []

    try:
        with open(file_path, "r", encoding="utf-8", errors="ignore") as f:
            for line_num, line in enumerate(f, start=1):
                # Skip comments
                if line.strip().startswith("#"):
                    continue

                # Check each forbidden pattern
                for pattern, pattern_name in FORBIDDEN_PATTERNS:
                    if re.search(pattern, line, re.IGNORECASE):
                        violations.append((line_num, pattern_name, line.strip()))

    except Exception as e:
        print(f"WARNING: Failed to scan {file_path}: {e}", file=sys.stderr)

    return violations


def scan_directory(root_path: Path, patterns: list[str]) -> dict[Path, list[tuple[int, str, str]]]:
    """
    Scan directory for files matching patterns.

    Args:
        root_path: Root directory to scan.
        patterns: List of glob patterns (e.g., "**/*.yaml").

    Returns:
        Dictionary mapping file paths to violation lists.
    """
    all_violations = {}

    for pattern in patterns:
        for file_path in root_path.glob(pattern):
            if file_path.is_file():
                violations = scan_file(file_path)
                if violations:
                    all_violations[file_path] = violations

    return all_violations


def main():
    parser = argparse.ArgumentParser(
        description="Runtime Secret Hygiene Checker",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  python scripts/runtime_secret_hygiene_check.py
  python scripts/runtime_secret_hygiene_check.py --relaxed
        """,
    )
    parser.add_argument(
        "--relaxed",
        action="store_true",
        help="Report violations as warnings only (exit 0)",
    )
    args = parser.parse_args()

    # Determine repository root
    script_dir = Path(__file__).resolve().parent
    repo_root = script_dir.parent

    # Scan paths configuration
    scan_configs = [
        (repo_root / "k8s", ["**/*.yaml", "**/*.yml"]),
        (repo_root, [".env*"]),
        (repo_root / "apps", ["**/.env*"]),
    ]

    # Run scans
    all_violations = {}
    for base_path, patterns in scan_configs:
        if base_path.exists():
            violations = scan_directory(base_path, patterns)
            all_violations.update(violations)

    # Print results
    if all_violations:
        severity = "WARNING" if args.relaxed else "ERROR"
        print(f"{severity}: Forbidden secrets detected in runtime configuration files")
        print()

        for file_path, violations in sorted(all_violations.items()):
            print(f"File: {file_path.relative_to(repo_root)}")
            for line_num, pattern_name, line_content in violations:
                print(f"  Line {line_num}: {pattern_name}")
                print(f"    {line_content}")
            print()

        if args.relaxed:
            print(f"PASS (relaxed): {len(all_violations)} file(s) with violations (warnings only)")
            sys.exit(0)
        else:
            print(f"FAIL: {len(all_violations)} file(s) with violations")
            print()
            print("Fix: Remove forbidden secrets from runtime configuration files.")
            print("See: dpp/docs/supabase/01_secrets_and_keys.md for guidance.")
            sys.exit(1)
    else:
        print("PASS: No forbidden secrets detected")
        sys.exit(0)


if __name__ == "__main__":
    main()
