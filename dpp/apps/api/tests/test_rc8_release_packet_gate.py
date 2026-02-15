"""
RC-8 Contract Gate: Release Packet Lock-in.

What RC-8 locks:
- External-ready release documentation exists and is accessible via HTTP
- Required sections are present in both RELEASE_NOTES and PILOT_READY
- No internal placeholders or sensitive info leaked to external docs

Gate-1: File existence + HTTP 200 response for release docs
Gate-2: Required sections present in docs
Gate-3: Leak-check for internal placeholders

NOTE:
These tests are expected to FAIL until RC-8 is implemented.
"""

from __future__ import annotations

import re
from pathlib import Path

import pytest
from fastapi.testclient import TestClient


# Internal info patterns that MUST NOT appear in external docs
INTERNAL_LEAK_PATTERNS = [
    "wiki.example.com",
    "PagerDuty",
    "@example.com",
    "prod-db.example.com",
    "internal wiki",
    "https://wiki.",
    "on-call",
    "pagerduty",
    "localhost",
    "127.0.0.1",
    "0.0.0.0",
]


def _get_repo_root() -> Path:
    """Find repo root by looking for dpp/ directory."""
    current = Path(__file__).resolve()
    for parent in [current, *current.parents]:
        if (parent / "dpp").is_dir():
            return parent
    raise RuntimeError(f"Could not find repo root from {__file__}")


def _check_required_sections(content: str, required_sections: list[str], doc_name: str) -> None:
    """Check that all required section headings are present in markdown content."""
    missing = []
    for section in required_sections:
        # Support alternative headings (e.g., "## Summary" or "## Highlights")
        if isinstance(section, tuple):
            if not any(heading.lower() in content.lower() for heading in section):
                missing.append(f"{section[0]} (or alternatives: {', '.join(section[1:])})")
        else:
            if section.lower() not in content.lower():
                missing.append(section)

    assert not missing, (
        f"{doc_name} missing required sections: {missing}\n\n"
        f"Content preview (first 500 chars):\n{content[:500]}"
    )


def _check_no_leaks(content: str, doc_name: str) -> None:
    """Check that content does not contain internal placeholders."""
    found_leaks = []
    content_lower = content.lower()

    for pattern in INTERNAL_LEAK_PATTERNS:
        if pattern.lower() in content_lower:
            # Find context around the leak
            pattern_lower = pattern.lower()
            idx = content_lower.find(pattern_lower)
            start = max(0, idx - 50)
            end = min(len(content), idx + len(pattern) + 50)
            context = content[start:end].replace('\n', ' ')
            found_leaks.append(f"  - '{pattern}' in: ...{context}...")

    assert not found_leaks, (
        f"{doc_name} contains internal placeholders that must be removed:\n"
        + "\n".join(found_leaks)
    )


@pytest.fixture
def app_for_static():
    """Create app instance to test static file serving."""
    from dpp_api.main import app
    return app


def test_gate_1_release_docs_exist_and_accessible(app_for_static):
    """Gate-1: Release docs MUST exist and be accessible via HTTP GET."""
    client = TestClient(app_for_static)

    # Test RELEASE_NOTES
    release_notes_resp = client.get("/RELEASE_NOTES_v0.4_RC.md")
    assert release_notes_resp.status_code == 200, (
        f"RELEASE_NOTES not accessible. Status: {release_notes_resp.status_code}\n"
        f"Expected: /RELEASE_NOTES_v0.4_RC.md to be served from dpp/public/"
    )

    # Test PILOT_READY
    pilot_ready_resp = client.get("/PILOT_READY.md")
    assert pilot_ready_resp.status_code == 200, (
        f"PILOT_READY not accessible. Status: {pilot_ready_resp.status_code}\n"
        f"Expected: /PILOT_READY.md to be served from dpp/public/"
    )

    # Sanity check: content is not empty
    assert len(release_notes_resp.text) > 100, "RELEASE_NOTES appears empty"
    assert len(pilot_ready_resp.text) > 100, "PILOT_READY appears empty"


def test_gate_2_required_sections_present(app_for_static):
    """Gate-2: Release docs MUST contain all required sections."""
    client = TestClient(app_for_static)

    # Get content
    release_notes = client.get("/RELEASE_NOTES_v0.4_RC.md").text
    pilot_ready = client.get("/PILOT_READY.md").text

    # RELEASE_NOTES required sections (support alternatives)
    release_sections = [
        ("## Highlights", "## Summary"),
        "## Changes",
        "## Known Issues",
        "## Rollback Plan",
        ("## Compatibility", "## Breaking Changes"),
    ]

    # PILOT_READY required sections
    pilot_sections = [
        "## Scope",
        "## Entry Criteria",
        "## Exit Criteria",
        "## Monitoring & Alerts",
        ("## Kill Switch", "## Stop Rules"),
    ]

    # Check sections
    for section in release_sections:
        if isinstance(section, tuple):
            # Alternative headings
            found = any(heading.lower() in release_notes.lower() for heading in section)
            assert found, (
                f"RELEASE_NOTES missing required section: {section[0]} "
                f"(alternatives: {', '.join(section[1:])})\n\n"
                f"Available headings: {[line for line in release_notes.split('\\n') if line.startswith('#')]}"
            )
        else:
            assert section.lower() in release_notes.lower(), (
                f"RELEASE_NOTES missing required section: {section}\n\n"
                f"Available headings: {[line for line in release_notes.split('\\n') if line.startswith('#')]}"
            )

    for section in pilot_sections:
        if isinstance(section, tuple):
            found = any(heading.lower() in pilot_ready.lower() for heading in section)
            assert found, (
                f"PILOT_READY missing required section: {section[0]} "
                f"(alternatives: {', '.join(section[1:])})\n\n"
                f"Available headings: {[line for line in pilot_ready.split('\\n') if line.startswith('#')]}"
            )
        else:
            assert section.lower() in pilot_ready.lower(), (
                f"PILOT_READY missing required section: {section}\n\n"
                f"Available headings: {[line for line in pilot_ready.split('\\n') if line.startswith('#')]}"
            )


def test_gate_3_no_internal_leaks(app_for_static):
    """Gate-3: Release docs MUST NOT contain internal placeholders or sensitive info."""
    client = TestClient(app_for_static)

    # Get content
    release_notes = client.get("/RELEASE_NOTES_v0.4_RC.md").text
    pilot_ready = client.get("/PILOT_READY.md").text

    # Check for leaks
    _check_no_leaks(release_notes, "RELEASE_NOTES_v0.4_RC.md")
    _check_no_leaks(pilot_ready, "PILOT_READY.md")
