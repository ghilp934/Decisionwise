"""RC-5 Contract Gate: Release Hygiene + API Inventory + Secrets Scanning.

This test acts as a pytest gate that runs all RC-5 verification scripts.
PASS requires all three scripts to exit with code 0.
"""

import subprocess
import sys
from pathlib import Path

import pytest


def run_script(script_name: str) -> tuple[int, str, str]:
    """Run RC-5 script and capture output.

    Args:
        script_name: Name of script (e.g., "rc5_release_hygiene_check.py")

    Returns:
        (exit_code, stdout, stderr)
    """
    repo_root = Path(__file__).parent.parent.parent.parent
    script_path = repo_root / "scripts" / script_name

    result = subprocess.run(
        [sys.executable, str(script_path)],
        capture_output=True,
        text=True,
        cwd=repo_root,
    )

    return result.returncode, result.stdout, result.stderr


class TestRC5Gate:
    """RC-5 Contract Gate: Release Hygiene + API Inventory + Secrets Scanning."""

    def test_rc5_release_hygiene(self):
        """RC-5.1: Release hygiene check (repo + docker images)."""
        exit_code, stdout, stderr = run_script("rc5_release_hygiene_check.py")

        # Print output for visibility
        if stdout:
            print("\n" + stdout)
        if stderr:
            print("\n" + stderr, file=sys.stderr)

        assert exit_code == 0, "Release hygiene check failed"

    def test_rc5_api_inventory(self):
        """RC-5.2: API inventory check (OpenAPI drift + hidden endpoints)."""
        exit_code, stdout, stderr = run_script("rc5_api_inventory.py")

        # Print output for visibility
        if stdout:
            print("\n" + stdout)
        if stderr:
            print("\n" + stderr, file=sys.stderr)

        assert exit_code == 0, "API inventory check failed"

    def test_rc5_sensitive_data_scan(self):
        """RC-5.3: Sensitive data scan (secrets detection with S1/S2 rules)."""
        exit_code, stdout, stderr = run_script("rc5_sensitive_data_scan.py")

        # Print output for visibility
        if stdout:
            print("\n" + stdout)
        if stderr:
            print("\n" + stderr, file=sys.stderr)

        assert exit_code == 0, "Sensitive data scan failed"

    def test_rc5_evidence_pack_exists(self):
        """RC-5.4: Verify all evidence pack files exist."""
        repo_root = Path(__file__).parent.parent.parent.parent
        evidence_dir = repo_root / "docs" / "rc" / "rc5"

        required_files = [
            "RC5_HIDDEN_ENDPOINT_ALLOWLIST.txt",
            "RC5_API_INVENTORY.md",
            "RC5_SENSITIVE_DATA_SCAN_REPORT.md",
        ]

        for filename in required_files:
            file_path = evidence_dir / filename
            assert file_path.exists(), f"Missing evidence file: {filename}"
