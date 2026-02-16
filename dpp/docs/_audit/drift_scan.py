#!/usr/bin/env python3
"""
Drift Scan - Forbidden Tokens Detection
Target: public/docs, docs/pilot, public/llms.txt, main.py
"""
import os
import re
from pathlib import Path
from datetime import datetime

# Configuration
BASE_DIR = Path(__file__).parent.parent.parent
OUTPUT_FILE = BASE_DIR / "docs" / "_audit" / "drift_inventory.txt"

SCAN_PATHS = [
    BASE_DIR / "public" / "docs",
    BASE_DIR / "docs" / "pilot",
    BASE_DIR / "public" / "llms.txt",
    BASE_DIR / "public" / "llms-full.txt",
    BASE_DIR / "apps" / "api" / "dpp_api" / "main.py",
]

FORBIDDEN_TOKENS = [
    "X-API-Key",
    "dw_live_",
    "dw_test_",
    "sk_live_",
    "sk_test_",
    "workspace_id",
    "plan_id",
    "Decision Credits",
]


def scan_file(file_path: Path, token: str) -> list[tuple[int, str]]:
    """Scan a single file for a token, return (line_number, line_content) list."""
    results = []
    try:
        with open(file_path, 'r', encoding='utf-8', errors='ignore') as f:
            for line_num, line in enumerate(f, 1):
                if token in line:
                    results.append((line_num, line.rstrip()))
    except Exception as e:
        pass  # Skip files that can't be read
    return results


def scan_path(search_path: Path, token: str) -> dict[str, list[tuple[int, str]]]:
    """Scan a path (file or directory) for a token."""
    findings = {}

    if not search_path.exists():
        return findings

    if search_path.is_file():
        results = scan_file(search_path, token)
        if results:
            findings[str(search_path.relative_to(BASE_DIR))] = results
    else:
        # Directory: scan all .md, .txt, .py files
        for ext in ['*.md', '*.txt', '*.py']:
            for file_path in search_path.rglob(ext):
                if file_path.is_file():
                    results = scan_file(file_path, token)
                    if results:
                        findings[str(file_path.relative_to(BASE_DIR))] = results

    return findings


def main():
    """Generate drift inventory report."""
    OUTPUT_FILE.parent.mkdir(parents=True, exist_ok=True)

    with open(OUTPUT_FILE, 'w', encoding='utf-8') as out:
        # Header
        out.write("=" * 80 + "\n")
        out.write("DRIFT INVENTORY - Forbidden Token Scan\n")
        out.write(f"Date: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n")
        out.write("Project: Decisionwise API Platform (Decisionproof)\n")
        out.write("=" * 80 + "\n\n")

        # Scan each token
        total_findings = 0
        for token in FORBIDDEN_TOKENS:
            out.write(f"## Scanning for: {token}\n\n")

            token_findings = {}
            for path in SCAN_PATHS:
                findings = scan_path(path, token)
                if findings:
                    token_findings.update(findings)

            if token_findings:
                for file_path, occurrences in sorted(token_findings.items()):
                    out.write(f"### Found in: {file_path}\n")
                    for line_num, line_content in occurrences:
                        out.write(f"  Line {line_num}: {line_content}\n")
                        total_findings += 1
                    out.write("\n")
            else:
                out.write("✓ No occurrences found\n\n")

        # Summary
        out.write("=" * 80 + "\n")
        out.write(f"SCAN COMPLETE - Total findings: {total_findings}\n")
        out.write("=" * 80 + "\n")

    # Print to console
    with open(OUTPUT_FILE, 'r', encoding='utf-8') as f:
        print(f.read())


if __name__ == "__main__":
    main()
