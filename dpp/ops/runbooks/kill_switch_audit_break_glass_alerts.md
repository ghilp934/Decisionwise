# Kill-Switch Audit Break-glass: WORM Governance Bypass Alert Runbook

**Runbook**: Phase 6.2 — WORM Break-glass Alerts (WHO/WHERE/WHAT hardening)
**Status**: Active
**Owner**: Platform Security
**Date**: 2026-02-21 (P6.2 updated — InputTransformer + simulation test added)

---

## Overview

Kill-switch audit records are stored in S3 with **Object Lock** (7-year retention).
The retention mode is configured via `KILL_SWITCH_AUDIT_WORM_MODE` (P5.8):

| Mode | Env Value | Bypass Possible? | Use Case |
|------|-----------|-----------------|----------|
| **GOVERNANCE** | `GOVERNANCE` | Yes — with `s3:BypassGovernanceRetention` IAM + explicit header | Pilot / pre-prod / break-glass possible |
| **COMPLIANCE** | `COMPLIANCE` | **No** — immutable; no principal can shorten retention or delete | Production locked / maximum audit integrity |

A **Governance bypass** (`bypassGovernanceRetention` or `x-amz-bypass-governance-retention: true`)
is a break-glass action that **must trigger immediate security review**.

### ⚠️ Alert Email Must Contain WHO / WHERE / WHAT

From Phase 6.2, every break-glass alert email body **must include** these 3 elements
to enable immediate 1st-level triage **without** logging into the AWS console:

| Element | Field | CloudTrail path |
|---------|-------|----------------|
| **WHO** | Actor IAM ARN | `$.detail.userIdentity.arn` |
| **WHERE** | Source IP | `$.detail.sourceIPAddress` |
| **WHAT** | Request parameters | `$.detail.requestParameters` |

These are injected via **EventBridge InputTransformer** (see Setup §3 below).

---

## Alert Architecture

```
S3 Governance Bypass Attempt (GOVERNANCE mode only)
        │  PutObjectRetention / DeleteObject /
        │  DeleteObjectVersion / PutObjectLegalHold
        │  + bypassGovernanceRetention=true
        ▼
  AWS CloudTrail (Data Events — WriteOnly, audit bucket)
        │
        ▼
  Amazon EventBridge Rule: KillSwitchAuditGovernanceBypass
  Pattern covers:
    Pattern A: requestParameters.x-amz-bypass-governance-retention = "true"
    Pattern B: requestParameters.bypassGovernanceRetention = true
        │
        ▼
  EventBridge InputTransformer
  (injects WHO / WHERE / WHAT into email body)
        │
        ▼
  Amazon SNS Topic: kill-switch-audit-break-glass-alerts
        │
        ▼
  Email Subscription: security-team@example.com
```

---

## Setup: Automated (Recommended)

Use the idempotent setup script to create/update all resources at once:

```bash
# Required env vars
export AUDIT_BUCKET_NAME="dpp-kill-switch-audit-prod"
export ALERT_EMAIL="security-team@example.com"
export AWS_REGION="ap-northeast-2"
export AWS_PROFILE="dpp-admin"

# Optional: if your CloudTrail trail has a different name
export TRAIL_NAME="dpp-audit-trail"

bash dpp/infra/scripts/p6_2_setup_breakglass_alerts.sh
```

The script performs steps 1–4 below automatically and prints a simulation test command.
Re-running is safe (idempotent).

---

## Setup: Step-by-Step (Manual)

### Step 1: CloudTrail Data Events

Enable CloudTrail **Data Events** on the audit bucket, **WriteOnly** to capture
all object-write/delete operations (including failed delete attempts on retention-locked objects).

```bash
aws cloudtrail put-event-selectors \
  --trail-name dpp-audit-trail \
  --event-selectors '[
    {
      "ReadWriteType": "WriteOnly",
      "IncludeManagementEvents": false,
      "DataResources": [
        {
          "Type": "AWS::S3::Object",
          "Values": ["arn:aws:s3:::YOUR_AUDIT_BUCKET_NAME/"]
        }
      ]
    }
  ]' \
  --profile dpp-admin
```

**Verify**:
```bash
aws cloudtrail get-event-selectors \
  --trail-name dpp-audit-trail \
  --query 'EventSelectors[?ReadWriteType==`WriteOnly`].DataResources' \
  --profile dpp-admin
```

Expected: output includes `arn:aws:s3:::YOUR_AUDIT_BUCKET_NAME/`.

> **Why WriteOnly?** We need to detect bypass write/delete operations. Read events
> would add noise and cost. For COMPLIANCE mode delete attempts (which always fail),
> WriteOnly still captures the attempt in CloudTrail because the API call is made
> before the access check that rejects it.

---

### Step 2: SNS Topic and Email Subscription

```bash
# Create topic (idempotent — returns existing ARN if already exists)
TOPIC_ARN=$(aws sns create-topic \
  --name kill-switch-audit-break-glass-alerts \
  --query TopicArn --output text \
  --profile dpp-admin)

# Subscribe email
aws sns subscribe \
  --topic-arn "${TOPIC_ARN}" \
  --protocol email \
  --notification-endpoint security-team@example.com \
  --profile dpp-admin
```

> **ACTION**: Confirm the subscription by clicking the link in the confirmation email.
> Alerts will NOT be delivered until the subscription is confirmed.

**Allow EventBridge to publish to this topic** (set topic policy):
```bash
ACCOUNT_ID=$(aws sts get-caller-identity --query Account --output text --profile dpp-admin)

aws sns set-topic-attributes \
  --topic-arn "${TOPIC_ARN}" \
  --attribute-name Policy \
  --attribute-value "{
    \"Version\":\"2012-10-17\",
    \"Statement\":[{
      \"Sid\":\"AllowEventBridgePublish\",
      \"Effect\":\"Allow\",
      \"Principal\":{\"Service\":\"events.amazonaws.com\"},
      \"Action\":\"sns:Publish\",
      \"Resource\":\"${TOPIC_ARN}\",
      \"Condition\":{\"ArnLike\":{\"aws:SourceArn\":\"arn:aws:events:ap-northeast-2:${ACCOUNT_ID}:rule/KillSwitchAuditGovernanceBypass\"}}
    }]
  }" \
  --profile dpp-admin
```

---

### Step 3: EventBridge Rule

The rule pattern covers **two bypass representations** seen in different AWS client versions:
- **Pattern A**: `requestParameters.x-amz-bypass-governance-retention = "true"` (HTTP header — older clients)
- **Pattern B**: `requestParameters.bypassGovernanceRetention = true` (SDK boolean — newer clients)

Rule template is managed in:
`dpp/infra/eventbridge/kill_switch_audit_breakglass_rule_v1.json`

Apply via script (recommended) or manually:

```bash
# Substitute bucket name in the template and apply
RULE_PATTERN=$(jq \
  --arg bucket "YOUR_AUDIT_BUCKET_NAME" \
  'walk(if type == "string" and . == "AUDIT_BUCKET_NAME_PLACEHOLDER" then $bucket else . end)
   | del(._comment, ._placeholders)' \
  dpp/infra/eventbridge/kill_switch_audit_breakglass_rule_v1.json)

aws events put-rule \
  --name "KillSwitchAuditGovernanceBypass" \
  --event-pattern "${RULE_PATTERN}" \
  --state ENABLED \
  --description "WORM break-glass: governance bypass on audit bucket (Phase 6.2)" \
  --profile dpp-admin
```

---

### Step 4: EventBridge Target with InputTransformer (WHO/WHERE/WHAT)

The InputTransformer injects WHO/WHERE/WHAT into the SNS email body so operators
can triage from the email alone — no console login required.

**InputPathsMap** (fields extracted from CloudTrail event):

| Placeholder | CloudTrail Path | Element |
|-------------|----------------|---------|
| `<arn>`     | `$.detail.userIdentity.arn` | **WHO** |
| `<ip>`      | `$.detail.sourceIPAddress` | **WHERE** |
| `<req>`     | `$.detail.requestParameters` | **WHAT** |
| `<event>`   | `$.detail.eventName` | Action type |
| `<time>`    | `$.detail.eventTime` | Timestamp |
| `<region>`  | `$.detail.awsRegion` | AWS region |
| `<account>` | `$.account` | AWS account |

**Email body template** (produced by InputTransformer):
```
[WORM BREAK-GLASS DETECTED]

event=DeleteObject
time=2026-02-21T00:00:00Z
region=ap-northeast-2
account=ACCOUNT_ID

--- WHO (actor) ---
actor_arn=arn:aws:sts::ACCOUNT_ID:assumed-role/dpp-break-glass-role/operator

--- WHERE (origin) ---
source_ip=203.0.113.1

--- WHAT (action) ---
request_parameters={"bucketName":"dpp-kill-switch-audit-prod","key":"kill-switch/2026/02/21/...","x-amz-bypass-governance-retention":"true"}

--- ACTION REQUIRED ---
1. Verify this was authorized (check incident ticket).
2. If unauthorized: revoke s3:BypassGovernanceRetention from actor role immediately.
3. Run: aws cloudtrail lookup-events --lookup-attributes AttributeKey=EventName,AttributeValue=DeleteObject
4. See runbook: dpp/ops/runbooks/kill_switch_audit_break_glass_alerts.md
```

Target template is managed in:
`dpp/infra/eventbridge/kill_switch_audit_breakglass_target_v1.json`

Apply via script (recommended) or manually:

```bash
TARGETS_JSON=$(jq \
  --arg arn "${TOPIC_ARN}" \
  '[.[] | walk(if type == "string" and . == "TOPIC_ARN_PLACEHOLDER" then $arn else . end)
    | del(._comment, ._placeholders)]' \
  dpp/infra/eventbridge/kill_switch_audit_breakglass_target_v1.json)

aws events put-targets \
  --rule "KillSwitchAuditGovernanceBypass" \
  --targets "${TARGETS_JSON}" \
  --profile dpp-admin
```

---

### Step 5: Simulation Test (Verify Email Delivery)

Do **not** wait for a real break-glass event. Use `put-events` to rehearse the
full pipeline and confirm the email body contains WHO/WHERE/WHAT.

```bash
# 1. Prepare sample event (substitute placeholders)
ACCOUNT_ID=$(aws sts get-caller-identity --query Account --output text --profile dpp-admin)

jq \
  --arg acct "${ACCOUNT_ID}" \
  --arg bucket "YOUR_AUDIT_BUCKET_NAME" \
  '(.Detail.userIdentity.arn |= gsub("ACCOUNT_ID_PLACEHOLDER"; $acct))
   | (.Detail.userIdentity.accountId |= $acct)
   | (.Detail.userIdentity.sessionContext.sessionIssuer.arn |= gsub("ACCOUNT_ID_PLACEHOLDER"; $acct))
   | (.Detail.userIdentity.sessionContext.sessionIssuer.accountId |= $acct)
   | (.Detail.resources[].ARN |= gsub("ACCOUNT_ID_PLACEHOLDER"; $acct))
   | (.Detail.resources[].accountId |= $acct)
   | (.Detail.requestParameters.bucketName |= $bucket)
   | (.Detail.resources[].ARN |= gsub("AUDIT_BUCKET_NAME_PLACEHOLDER"; $bucket))' \
  dpp/infra/samples/cloudtrail_s3_breakglass_sample_event_v1.json \
  > /tmp/breakglass_test_event.json

# 2. Send test event to EventBridge default bus
aws events put-events \
  --entries "$(jq '[.]' /tmp/breakglass_test_event.json)" \
  --region ap-northeast-2 \
  --profile dpp-admin

# 3. Check email inbox within 60 seconds for subject containing:
#    "WORM BREAK-GLASS DETECTED"
#
# Verify the email body contains:
#   actor_arn=arn:aws:sts::ACCOUNT_ID:assumed-role/dpp-break-glass-role/break-glass-operator
#   source_ip=203.0.113.1
#   request_parameters={"bucketName":"...","x-amz-bypass-governance-retention":"true"}
```

> **Test isolation**: Use a dedicated `[TEST]` subject prefix or a test-only SNS subscription
> if running in a shared production account. Add `--subject "[TEST] WORM break-glass"` to
> the SNS subscription filter policy if needed.

---

## When the Alert Fires: Response Procedure

### Email Triage (first 5 minutes — from email alone)

The email body contains all 3 required elements:

1. **WHO** (`actor_arn`): Identify the IAM role/user that performed the bypass.
2. **WHERE** (`source_ip`): Verify origin matches a known operator workstation/VPN.
3. **WHAT** (`request_parameters`): Confirm which object(s) were targeted.

If all 3 match an active, pre-approved change request → continue to §Investigation.
If any element is unexpected → **immediately escalate to P0 security incident**.

### Immediate Actions (within 15 minutes)

1. **Identify the actor**: From the email `actor_arn` field.
   - Cross-reference with the CloudTrail console for the full event chain.

2. **Verify authorization**:
   - Check the incident ticket / change request system.
   - Contact the actor's team lead.
   - If unauthorized → escalate to P0 security incident immediately.

3. **Assess scope**: Check for deleted/overwritten records.
   ```bash
   aws s3api list-object-versions \
     --bucket YOUR_AUDIT_BUCKET_NAME \
     --prefix kill-switch/ \
     --profile dpp-admin
   ```

4. **Freeze further bypass**: Revoke `s3:BypassGovernanceRetention` from the actor's IAM role.

### Investigation (within 1 hour)

5. **Pull CloudTrail events** for the last 24 hours:
   ```bash
   aws cloudtrail lookup-events \
     --lookup-attributes AttributeKey=EventName,AttributeValue=DeleteObject \
     --start-time $(date -u -d "24 hours ago" +%Y-%m-%dT%H:%M:%SZ) \
     --profile dpp-admin
   ```

6. **Verify audit record integrity**: Confirm which kill-switch audit records exist
   and whether any gaps exist in the timeline.

7. **Document**: Record the bypass event, actor, justification (or lack thereof),
   and remediation actions taken.

### Escalation

| Severity | Condition | Action |
|----------|-----------|--------|
| P0 | Unauthorized bypass detected | Immediate security incident; notify CISO |
| P1 | Authorized but undocumented bypass | Post-hoc change request required within 24h |
| P2 | Test/dev bypass in non-prod | Document and ensure prod bucket is unaffected |

---

## Prevention: IAM Policy

Restrict `s3:BypassGovernanceRetention` to a dedicated break-glass role only.
Apply this policy as a **Service Control Policy (SCP)** or bucket policy:

```json
{
  "Sid": "DenyGovernanceBypassExceptBreakGlass",
  "Effect": "Deny",
  "NotPrincipal": {
    "AWS": "arn:aws:iam::ACCOUNT_ID_PLACEHOLDER:role/dpp-break-glass-role"
  },
  "Action": "s3:BypassGovernanceRetention",
  "Resource": "arn:aws:s3:::YOUR_AUDIT_BUCKET_NAME/*"
}
```

> **IMPORTANT**: The application service role (`dpp-api`) must NOT hold
> `s3:BypassGovernanceRetention`. Verify this after every IAM policy change.

---

## P5.8: WORM Mode Selection Guide

### GOVERNANCE (Pilot / Default)

Set `KILL_SWITCH_AUDIT_WORM_MODE=GOVERNANCE`.

- Objects can be deleted or retention-shortened ONLY with:
  1. IAM permission `s3:BypassGovernanceRetention` on the actor's role, AND
  2. Explicit `x-amz-bypass-governance-retention: true` header on the request
- Our service role (`dpp-api`) MUST NOT hold `s3:BypassGovernanceRetention`
- Break-glass: A dedicated break-glass role may hold this permission
- All bypass attempts trigger CloudTrail events → EventBridge → SNS alert (this runbook)

**Recommended for**: Pilot cutover, staging, or any environment where emergency
record deletion may be operationally required (e.g., GDPR erasure with approval).

### COMPLIANCE (Production Locked)

Set `KILL_SWITCH_AUDIT_WORM_MODE=COMPLIANCE`.

- Objects **cannot** be deleted by **any** user, including root
- Delete attempts return `ObjectLockConfigurationError` — CloudTrail still records them
- There is no bypass mechanism; break-glass procedure cannot override COMPLIANCE locks

**Recommended for**: Production environments where audit integrity is paramount.

### Required Mode Validation (P5.8)

When `KILL_SWITCH_AUDIT_REQUIRED=1`, operators MUST set `KILL_SWITCH_AUDIT_WORM_MODE`.
If not set, the application raises `AuditSinkConfigError (WORM_MODE_REQUIRED_BUT_NOT_SET)`.

```bash
# Correct: GOVERNANCE for pilot
KILL_SWITCH_AUDIT_REQUIRED=1
KILL_SWITCH_AUDIT_BUCKET=dpp-audit-prod
KILL_SWITCH_AUDIT_WORM_MODE=GOVERNANCE

# Correct: COMPLIANCE for locked production
KILL_SWITCH_AUDIT_REQUIRED=1
KILL_SWITCH_AUDIT_BUCKET=dpp-audit-prod
KILL_SWITCH_AUDIT_WORM_MODE=COMPLIANCE

# WRONG: Will fail with WORM_MODE_REQUIRED_BUT_NOT_SET
KILL_SWITCH_AUDIT_REQUIRED=1
KILL_SWITCH_AUDIT_BUCKET=dpp-audit-prod
# KILL_SWITCH_AUDIT_WORM_MODE not set → AuditSinkConfigError at boot
```

---

## P5.9: Fingerprint (HMAC + Kid) Environment Variables

| Env Var | Required? | Description | Production Guidance |
|---------|-----------|-------------|---------------------|
| `KILL_SWITCH_AUDIT_FINGERPRINT_KID` | No (default: `kid_dev`) | Key-ID prefix. Use `kid_YYYYMM` convention. | Set in deployment manifest. Not a secret. |
| `KILL_SWITCH_AUDIT_FINGERPRINT_PEPPER_B64` | When REQUIRED=1 or STRICT=1 | Base64-encoded HMAC pepper (preferred). | Store in AWS Secrets Manager. Inject via ASCP. Never commit. |
| `KILL_SWITCH_AUDIT_FINGERPRINT_PEPPER` | When REQUIRED=1 or STRICT=1 | UTF-8 pepper string (fallback/dev). | Same treatment as B64. Use B64 in production. |

### Pepper Rotation Procedure

1. `openssl rand -base64 32` → new secret in AWS Secrets Manager
2. New kid: `kid_YYYYMM` (e.g., `kid_202603` for March 2026)
3. Deploy: set `KILL_SWITCH_AUDIT_FINGERPRINT_KID=kid_202603` + new B64 pepper
4. Archive old pepper: store mapping `kid_202602 → <old_secret_arn>` in key registry
5. Do NOT delete historical WORM records — verifiable with archived old pepper

---

## Infra Files (Phase 6.2)

| File | Purpose |
|------|---------|
| `dpp/infra/eventbridge/kill_switch_audit_breakglass_rule_v1.json` | EventBridge event pattern (both bypass patterns, bucket-scoped) |
| `dpp/infra/eventbridge/kill_switch_audit_breakglass_target_v1.json` | SNS target + InputTransformer (WHO/WHERE/WHAT) |
| `dpp/infra/samples/cloudtrail_s3_breakglass_sample_event_v1.json` | Simulation test event for `put-events` |
| `dpp/infra/scripts/p6_2_setup_breakglass_alerts.sh` | Idempotent setup script (all 4 steps) |

---

## Related Runbooks

- `kill_switch_audit_worm.md` — WORM audit sink setup and STRICT mode configuration
- `secrets_ascp_irsa.md` — IRSA / IAM role management
- `db_backup_restore.md` — General data recovery procedures

---

## References

- [AWS S3 Object Lock: Governance Mode](https://docs.aws.amazon.com/AmazonS3/latest/userguide/object-lock-overview.html)
- [AWS EventBridge InputTransformer](https://docs.aws.amazon.com/eventbridge/latest/userguide/eb-transform-target-input.html)
- [CloudTrail S3 Data Events](https://docs.aws.amazon.com/awscloudtrail/latest/userguide/logging-data-events-with-cloudtrail.html)
- [EventBridge $or patterns](https://docs.aws.amazon.com/eventbridge/latest/userguide/eb-event-patterns.html)
- `dpp/apps/api/dpp_api/audit/sinks.py` — S3WormAuditSink implementation (P5.8)
- `dpp/apps/api/dpp_api/audit/kill_switch_audit.py` — fingerprint_token() HMAC (P5.9)
- `dpp/docs/decisions/DEC-P05-LOG-MASKING-WORM.md` — P5.3 WORM design decisions
