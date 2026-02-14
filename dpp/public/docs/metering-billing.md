# Metering & Billing

## Billable Status Codes

Decisionproof charges Decision Credits (DC) only for successful executions and business logic errors:

### Billable (2xx + 422)

- **2xx Success**: 200, 201, 204 (decision executed successfully)
- **422 Unprocessable Entity**: Valid request format, invalid business logic (e.g., invalid plan configuration)

## Non-Billable Status Codes

All client errors (except 422) and server errors are **non-billable**:

### Client Errors (4xx)

- **400 Bad Request**: Malformed JSON, missing required fields
- **401 Unauthorized**: Invalid or missing API key
- **403 Forbidden**: Insufficient permissions
- **404 Not Found**: Resource does not exist
- **409 Conflict**: Resource state conflict
- **412 Precondition Failed**: Condition not met
- **413 Payload Too Large**: Request body exceeds limit
- **415 Unsupported Media Type**: Invalid Content-Type
- **429 Too Many Requests**: Rate limit or quota exceeded

### Server Errors (5xx)

- **500 Internal Server Error**
- **502 Bad Gateway**
- **503 Service Unavailable**
- **504 Gateway Timeout**

## Idempotency (Duplicate Charge Prevention)

Decisionproof prevents duplicate charges using **idempotent metering**.

### How It Works

1. Include a unique `run_id` in every request
2. Same `(workspace_id, run_id)` pair is charged only once
3. Idempotency keys are retained for **45 days**
4. Duplicate requests return `deduplication_status: "duplicate"` with `dc_charged: 0`

### Example

```bash
# Request 1
curl -X POST /v1/runs \
  -d '{"workspace_id": "ws_123", "run_id": "run_001", ...}'
# Response: dc_charged=10, deduplication_status="new"

# Request 2 (duplicate)
curl -X POST /v1/runs \
  -d '{"workspace_id": "ws_123", "run_id": "run_001", ...}'
# Response: dc_charged=0, deduplication_status="duplicate"

# Request 3 (different run_id)
curl -X POST /v1/runs \
  -d '{"workspace_id": "ws_123", "run_id": "run_002", ...}'
# Response: dc_charged=10, deduplication_status="new"
```

### Atomic Guarantee

Idempotency checks use atomic Redis `SET NX EX` operations to prevent race conditions (TOCTOU-safe).

## Metering Response Fields

Every billable request returns metering information:

```json
{
  "event_id": "run_001",
  "deduplication_status": "new",
  "dc_charged": 10,
  "workspace_remaining_dc": 1990
}
```

- **event_id**: Same as `run_id`
- **deduplication_status**: `"new"` or `"duplicate"`
- **dc_charged**: Decision Credits charged for this request (0 if duplicate or non-billable)
- **workspace_remaining_dc**: Remaining DC quota for the month

## Billing Rules Summary

| Status Code | Billable | Example                          |
|-------------|----------|----------------------------------|
| 200         | ✅ Yes   | Successful decision execution    |
| 422         | ✅ Yes   | Invalid plan configuration       |
| 400         | ❌ No    | Malformed JSON                   |
| 401         | ❌ No    | Missing API key                  |
| 403         | ❌ No    | Insufficient permissions         |
| 404         | ❌ No    | Plan not found                   |
| 429         | ❌ No    | Rate limit exceeded              |
| 500         | ❌ No    | Server error                     |

See [Pricing SSoT](/pricing/ssot.json) for complete billing rules configuration.
