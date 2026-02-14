# Quickstart

## Base URL

```
Production: https://api.decisionwise.ai
Sandbox:    https://sandbox-api.decisionwise.ai
```

## Authentication

Include your API key in the `X-API-Key` header:

```bash
X-API-Key: dw_live_abc123...
```

Sandbox keys use `dw_test_` prefix.

## Example Requests

### 200 Success (Billable)

```bash
curl -X POST https://api.decisionwise.ai/v1/runs \
  -H "X-API-Key: dw_live_abc123..." \
  -H "Content-Type: application/json" \
  -d '{
    "workspace_id": "ws_123",
    "run_id": "run_unique_001",
    "plan_id": "plan_456",
    "input": {"question": "What is 2+2?"}
  }'
```

**Response**: 200 OK + Decision result. **Billable** (charges Decision Credits).

### 422 Unprocessable Entity (Billable)

```bash
curl -X POST https://api.decisionwise.ai/v1/runs \
  -H "X-API-Key: dw_live_abc123..." \
  -H "Content-Type: application/json" \
  -d '{
    "workspace_id": "ws_123",
    "run_id": "run_unique_002",
    "plan_id": "plan_invalid",
    "input": {}
  }'
```

**Response**: 422 Unprocessable Entity (application/problem+json). **Billable** per pricing rules.

### 429 Rate Limit Exceeded (Non-Billable)

```bash
# After exceeding 600 requests/minute (STARTER tier)
curl -X POST https://api.decisionwise.ai/v1/runs \
  -H "X-API-Key: dw_live_abc123..." \
  -H "Content-Type: application/json" \
  -d '{
    "workspace_id": "ws_123",
    "run_id": "run_unique_603",
    "plan_id": "plan_456",
    "input": {"question": "Test"}
  }'
```

**Response**: 429 Too Many Requests (application/problem+json) with `violated-policies` field. **Non-billable**.
**Action**: Wait for `Retry-After` seconds, then retry.

## Idempotency Rule

**Include a unique `run_id` in every request.**
Same `(workspace_id, run_id)` pair is charged only once within 45 days.

Example:
- Request 1: `run_id: "run_001"` → Charged
- Request 2: `run_id: "run_001"` (duplicate) → Not charged (deduplication_status: "duplicate")
- Request 3: `run_id: "run_002"` → Charged
