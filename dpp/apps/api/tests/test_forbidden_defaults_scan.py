"""
T3: Regression "forbidden defaults" scan test.

Ops Hardening v2: Verify runtime modules do NOT contain hardcoded localhost defaults.
"""

import os
import re
from pathlib import Path


def test_no_localhost_4566_in_sqs_client():
    """
    T3-A: SQS client MUST NOT contain "localhost:4566" hardcoded defaults.

    Forbidden pattern: Any reference to "localhost:4566" or "127.0.0.1:4566" in runtime code.
    Allowed: Test files, docs, comments only.
    """
    # Get project root (assumes test is in dpp/apps/api/tests/)
    test_dir = Path(__file__).parent
    sqs_client_path = test_dir.parent / "dpp_api" / "queue" / "sqs_client.py"

    assert sqs_client_path.exists(), f"SQS client not found: {sqs_client_path}"

    with open(sqs_client_path, "r", encoding="utf-8") as f:
        content = f.read()

    # Remove comments and docstrings to avoid false positives
    # Simple heuristic: remove lines starting with # or inside """ """
    lines = content.split("\n")
    code_lines = []
    in_docstring = False

    for line in lines:
        stripped = line.strip()

        # Toggle docstring state
        if '"""' in stripped or "'''" in stripped:
            # Count quotes to handle single-line docstrings
            triple_double = stripped.count('"""')
            triple_single = stripped.count("'''")
            if (triple_double + triple_single) % 2 == 1:
                in_docstring = not in_docstring
            continue

        # Skip comments and docstrings
        if in_docstring or stripped.startswith("#"):
            continue

        code_lines.append(line)

    code_only = "\n".join(code_lines)

    # T3-A: Assert "localhost:4566" and "127.0.0.1:4566" NOT in runtime code
    forbidden_patterns = [
        r"localhost:4566",
        r"127\.0\.0\.1:4566",
        r'"http://localhost:4566',  # Quoted URL
        r"'http://localhost:4566",  # Single-quoted URL
    ]

    for pattern in forbidden_patterns:
        matches = re.findall(pattern, code_only, re.IGNORECASE)
        assert not matches, (
            f"Forbidden pattern '{pattern}' found in {sqs_client_path}:\n"
            f"  Matches: {matches}\n"
            f"  This violates Ops Hardening v2: NO hardcoded localhost defaults in production code."
        )


def test_no_silent_bucket_default_in_s3_client():
    """
    T3-B: S3 client MUST NOT contain silent "dpp-results" default bucket.

    Forbidden pattern: Default value "dpp-results" in bucket resolution.
    """
    test_dir = Path(__file__).parent
    s3_client_path = test_dir.parent / "dpp_api" / "storage" / "s3_client.py"

    assert s3_client_path.exists(), f"S3 client not found: {s3_client_path}"

    with open(s3_client_path, "r", encoding="utf-8") as f:
        content = f.read()

    # Remove comments and docstrings (same as above)
    lines = content.split("\n")
    code_lines = []
    in_docstring = False

    for line in lines:
        stripped = line.strip()

        if '"""' in stripped or "'''" in stripped:
            triple_double = stripped.count('"""')
            triple_single = stripped.count("'''")
            if (triple_double + triple_single) % 2 == 1:
                in_docstring = not in_docstring
            continue

        if in_docstring or stripped.startswith("#"):
            continue

        code_lines.append(line)

    code_only = "\n".join(code_lines)

    # T3-B: Assert silent default "dpp-results" NOT used as fallback in os.getenv()
    # Pattern: os.getenv(..., "dpp-results")  <- this is forbidden
    forbidden_pattern = r'os\.getenv\([^)]*,\s*["\']dpp-results["\']\s*\)'

    matches = re.findall(forbidden_pattern, code_only)
    assert not matches, (
        f"Forbidden silent default bucket 'dpp-results' found in {s3_client_path}:\n"
        f"  Matches: {matches}\n"
        f"  This violates Ops Hardening v2: NO silent bucket defaults (must fail-fast)."
    )


def test_config_env_module_exists():
    """
    T3-C: Verify centralized config/env.py module exists.

    Ops Hardening v2: Canonical env resolution should be centralized.
    """
    test_dir = Path(__file__).parent
    config_env_path = test_dir.parent / "dpp_api" / "config" / "env.py"

    assert config_env_path.exists(), (
        f"config/env.py not found: {config_env_path}\n"
        f"Ops Hardening v2 requires centralized env resolution helpers."
    )

    # Verify helper functions exist
    with open(config_env_path, "r", encoding="utf-8") as f:
        content = f.read()

    required_functions = [
        "get_s3_result_bucket",
        "get_sqs_queue_url",
        "is_localstack_endpoint",
    ]

    for func_name in required_functions:
        assert f"def {func_name}" in content, (
            f"Required helper '{func_name}' not found in config/env.py"
        )
