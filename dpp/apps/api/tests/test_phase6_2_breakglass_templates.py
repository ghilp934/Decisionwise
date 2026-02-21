"""Phase 6.2: Static validation of break-glass EventBridge/SNS templates.

Coverage (all static — no AWS calls, no network):
  T1) rule_v1.json parses as valid JSON
  T2) target_v1.json parses as valid JSON
  T3) InputPathsMap contains WHO/WHERE/WHAT paths
  T4) InputTemplate contains <arn> / <ip> / <req> placeholders
  T5) Rule event pattern covers required EventNames
  T6) Rule event pattern covers both bypass patterns (Pattern A + Pattern B)
  T7) Sample event has required CloudTrail structure (userIdentity/sourceIPAddress/requestParameters)
  T8) No real AWS account IDs (12-digit numbers) appear in any infra JSON file
"""

from __future__ import annotations

import json
import re
from pathlib import Path

import pytest

# ---------------------------------------------------------------------------
# Path setup
# ---------------------------------------------------------------------------

# dpp/apps/api/tests/test_phase6_2_breakglass_templates.py
# → up 4 levels → repo root → dpp/infra/
_TESTS_DIR = Path(__file__).parent
_REPO_ROOT = _TESTS_DIR.parents[3]   # dpp/apps/api → dpp → repo root
_DPP_DIR = _REPO_ROOT / "dpp"
_INFRA_DIR = _DPP_DIR / "infra"

RULE_JSON = _INFRA_DIR / "eventbridge" / "kill_switch_audit_breakglass_rule_v1.json"
TARGET_JSON = _INFRA_DIR / "eventbridge" / "kill_switch_audit_breakglass_target_v1.json"
SAMPLE_EVENT_JSON = _INFRA_DIR / "samples" / "cloudtrail_s3_breakglass_sample_event_v1.json"


# ---------------------------------------------------------------------------
# T1: Rule JSON parses
# ---------------------------------------------------------------------------

def test_t1_rule_json_is_valid():
    """T1: kill_switch_audit_breakglass_rule_v1.json is valid JSON."""
    assert RULE_JSON.exists(), f"Rule JSON not found: {RULE_JSON}"
    data = json.loads(RULE_JSON.read_text(encoding="utf-8"))
    assert isinstance(data, dict)


# ---------------------------------------------------------------------------
# T2: Target JSON parses
# ---------------------------------------------------------------------------

def test_t2_target_json_is_valid():
    """T2: kill_switch_audit_breakglass_target_v1.json is valid JSON (list)."""
    assert TARGET_JSON.exists(), f"Target JSON not found: {TARGET_JSON}"
    data = json.loads(TARGET_JSON.read_text(encoding="utf-8"))
    assert isinstance(data, list), "Target JSON must be a list (array of targets)"
    assert len(data) >= 1, "Target JSON must have at least one target"


# ---------------------------------------------------------------------------
# T3: InputPathsMap has WHO / WHERE / WHAT paths
# ---------------------------------------------------------------------------

def test_t3_input_paths_map_has_who_where_what():
    """T3: InputPathsMap maps arn (WHO), ip (WHERE), req (WHAT) from CloudTrail paths."""
    data = json.loads(TARGET_JSON.read_text(encoding="utf-8"))
    target = data[0]

    assert "InputTransformer" in target, "Target must have InputTransformer"
    transformer = target["InputTransformer"]
    assert "InputPathsMap" in transformer, "InputTransformer must have InputPathsMap"

    paths = transformer["InputPathsMap"]

    # WHO: actor ARN
    assert "arn" in paths, "InputPathsMap missing 'arn' (WHO)"
    assert "userIdentity" in paths["arn"], (
        f"WHO path should reference userIdentity.arn, got: {paths['arn']!r}"
    )

    # WHERE: source IP
    assert "ip" in paths, "InputPathsMap missing 'ip' (WHERE)"
    assert "sourceIPAddress" in paths["ip"], (
        f"WHERE path should reference sourceIPAddress, got: {paths['ip']!r}"
    )

    # WHAT: request parameters
    assert "req" in paths, "InputPathsMap missing 'req' (WHAT)"
    assert "requestParameters" in paths["req"], (
        f"WHAT path should reference requestParameters, got: {paths['req']!r}"
    )


# ---------------------------------------------------------------------------
# T4: InputTemplate has <arn> / <ip> / <req> placeholders
# ---------------------------------------------------------------------------

def test_t4_input_template_has_all_placeholders():
    """T4: InputTemplate includes <arn> (WHO), <ip> (WHERE), <req> (WHAT) placeholders."""
    data = json.loads(TARGET_JSON.read_text(encoding="utf-8"))
    template = data[0]["InputTransformer"]["InputTemplate"]

    assert "<arn>" in template, "InputTemplate missing <arn> placeholder (WHO)"
    assert "<ip>" in template, "InputTemplate missing <ip> placeholder (WHERE)"
    assert "<req>" in template, "InputTemplate missing <req> placeholder (WHAT)"


# ---------------------------------------------------------------------------
# T5: Rule covers required EventNames
# ---------------------------------------------------------------------------

def test_t5_rule_covers_required_event_names():
    """T5: Rule eventName list includes PutObjectRetention and DeleteObject at minimum."""
    data = json.loads(RULE_JSON.read_text(encoding="utf-8"))

    # EventName may be at detail level or inside $or branches
    rule_str = json.dumps(data)

    required_events = ["PutObjectRetention", "DeleteObject", "DeleteObjectVersion"]
    for event_name in required_events:
        assert event_name in rule_str, (
            f"EventBridge rule does not cover '{event_name}' — add it to eventName list"
        )


# ---------------------------------------------------------------------------
# T6: Rule covers both bypass patterns (Pattern A + Pattern B)
# ---------------------------------------------------------------------------

def test_t6_rule_covers_both_bypass_patterns():
    """T6: Rule detects both x-amz-bypass-governance-retention (A) and bypassGovernanceRetention (B)."""
    data = json.loads(RULE_JSON.read_text(encoding="utf-8"))
    rule_str = json.dumps(data)

    # Pattern A: HTTP header form
    assert "x-amz-bypass-governance-retention" in rule_str, (
        "Rule missing Pattern A: x-amz-bypass-governance-retention (HTTP header form)"
    )

    # Pattern B: SDK boolean form
    assert "bypassGovernanceRetention" in rule_str, (
        "Rule missing Pattern B: bypassGovernanceRetention (SDK boolean form)"
    )


# ---------------------------------------------------------------------------
# T7: Sample event has required CloudTrail structure
# ---------------------------------------------------------------------------

def test_t7_sample_event_has_cloudtrail_structure():
    """T7: Simulation sample event has Source/DetailType/Detail with CloudTrail fields."""
    assert SAMPLE_EVENT_JSON.exists(), f"Sample event not found: {SAMPLE_EVENT_JSON}"
    data = json.loads(SAMPLE_EVENT_JSON.read_text(encoding="utf-8"))

    assert "Source" in data, "Sample event missing Source"
    assert data["Source"] == "aws.s3", f"Source should be 'aws.s3', got {data['Source']!r}"
    assert "DetailType" in data
    assert "Detail" in data

    detail = data["Detail"]
    assert "userIdentity" in detail, "Detail missing userIdentity (WHO)"
    assert "arn" in detail["userIdentity"], "userIdentity missing arn"
    assert "sourceIPAddress" in detail, "Detail missing sourceIPAddress (WHERE)"
    assert "requestParameters" in detail, "Detail missing requestParameters (WHAT)"
    assert "x-amz-bypass-governance-retention" in detail["requestParameters"], (
        "Sample event should include bypass governance retention parameter"
    )


# ---------------------------------------------------------------------------
# T8: No real AWS account IDs (12-digit numbers) in infra JSON files
# ---------------------------------------------------------------------------

def test_t8_no_real_account_ids_in_infra_files():
    """T8: Phase 6.2 infra JSON files (eventbridge/ + samples/) have no real 12-digit AWS account IDs."""
    real_account_pattern = re.compile(r'\b\d{12}\b')

    # Scope to Phase 6.2 directories only (eventbridge/ and samples/)
    # Other legacy infra files are outside Phase 6.2 scope.
    p6_2_dirs = [
        _INFRA_DIR / "eventbridge",
        _INFRA_DIR / "samples",
    ]

    for scan_dir in p6_2_dirs:
        for json_file in scan_dir.rglob("*.json"):
            content = json_file.read_text(encoding="utf-8")
            matches = real_account_pattern.findall(content)
            assert not matches, (
                f"{json_file.relative_to(_DPP_DIR)} contains what looks like a real "
                f"AWS account ID (12-digit number): {matches}. "
                "Use ACCOUNT_ID_PLACEHOLDER instead."
            )
