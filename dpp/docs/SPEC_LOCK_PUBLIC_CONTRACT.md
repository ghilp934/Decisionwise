# SPEC LOCK: Public Contract v0.4.2.2

**Status**: LOCKED (Single Source of Truth)
**Effective Date**: 2026-02-17
**Project**: Decisionwise API Platform (Decisionproof)
**Purpose**: This document defines the **immutable public API contract** for v0.4.2.2. All documentation (public/docs, pilot docs, llms.txt) and machine-readable specs (function-calling-specs.json, OpenAPI) MUST conform to this specification.

---

## 1. Authentication (LOCK)

### 1.1 Header Format
- **Header Name**: `Authorization`
- **Scheme**: `Bearer`
- **Token Format**: `sk_{key_id}_{secret}`
  - Example: `sk_abc123_xyz789def456...`
  - **NO environment prefix** (no `sk_live_` or `sk_test_`)

### 1.2 Request Example
```http
POST /v1/runs HTTP/1.1
Host: api.decisionproof.ai
Authorization: Bearer sk_abc123_xyz789def456...
Idempotency-Key: unique-request-id-12345
Content-Type: application/json
```

### 1.3 FORBIDDEN (Documentation Ban)
- ❌ `X-API-Key` header (removed, not supported)
- ❌ Key format `dw_live_*` or `dw_test_*` (legacy, replaced)
- ❌ Key format `sk_live_*` or `sk_test_*` (environment prefix removed)

### 1.4 Error Responses
- **401 Unauthorized**: Missing or invalid `Authorization` header
- **403 Forbidden**: Valid token but insufficient permissions (tenant mismatch)

---

## 2. Runs API (LOCK)

### 2.1 POST /v1/runs - Create Run (Async)

#### Request
- **Method**: `POST /v1/runs`
- **Status**: `202 Accepted` (asynchronous operation)
- **Headers**:
  - `Authorization: Bearer sk_{key_id}_{secret}` (REQUIRED)
  - `Idempotency-Key: <unique-id>` (REQUIRED for duplicate prevention)
  - `Content-Type: application/json`

#### Request Body (RunCreateRequest)
```json
{
  "pack_type": "decision",
  "inputs": {
    "question": "Should we proceed with Plan A?",
    "context": {...}
  },
  "reservation": {
    "max_cost_usd": "0.0500",
    "timebox_sec": 90,
    "min_reliability_score": 0.8
  },
  "meta": {
    "trace_id": "optional-trace-id"
  }
}
```

**Schema Requirements**:
- `pack_type` (string, required): Pack type identifier
- `inputs` (object, required): Pack-specific inputs
- `reservation` (object, required):
  - `max_cost_usd` (string, required): 4 decimal places max (e.g., "0.0050")
  - `timebox_sec` (integer, optional): 1-90, default 90
  - `min_reliability_score` (float, optional): 0.0-1.0, default 0.8
- `meta` (object, optional):
  - `trace_id` (string, optional): Distributed tracing ID

#### Response (202 Accepted - RunReceipt)
```json
{
  "run_id": "run_abc123def456...",
  "status": "queued",
  "poll": {
    "href": "/v1/runs/run_abc123def456...",
    "recommended_interval_ms": 1500,
    "max_wait_sec": 90
  },
  "reservation": {
    "reserved_usd": "0.0500"
  },
  "meta": {
    "trace_id": "optional-trace-id",
    "profile_version": "v0.4.2.2"
  }
}
```

### 2.2 GET /v1/runs/{run_id} - Poll Run Status

#### Request
```http
GET /v1/runs/run_abc123def456... HTTP/1.1
Authorization: Bearer sk_abc123_xyz789...
```

#### Response (200 OK - RunStatusResponse)
```json
{
  "run_id": "run_abc123def456...",
  "status": "completed",
  "money_state": "settled",
  "cost": {
    "reserved_usd": "0.0500",
    "used_usd": "0.0120",
    "minimum_fee_usd": "0.0010",
    "budget_remaining_usd": "99.9880"
  },
  "result": {
    "presigned_url": "https://s3.amazonaws.com/...",
    "sha256": "abc123...",
    "expires_at": "2026-02-17T12:00:00Z"
  },
  "error": null,
  "meta": {
    "trace_id": "optional-trace-id",
    "profile_version": "v0.4.2.2"
  }
}
```

**Status Values** (Enum):
- `queued`: Submitted, awaiting worker
- `processing`: Worker executing
- `completed`: Success, result available
- `failed`: Error occurred
- `expired`: Exceeded retention period (410 Gone)

**Money State Values** (Enum):
- `reserved`: Budget locked, not yet settled
- `settled`: Final cost charged
- `refunded`: Partial refund issued (failure/cancellation)

### 2.3 GET /v1/tenants/{tenant_id}/usage - Usage Summary

#### Request
```http
GET /v1/tenants/tenant_abc123/usage HTTP/1.1
Authorization: Bearer sk_abc123_xyz789...
```

#### Response (200 OK)
```json
{
  "tenant_id": "tenant_abc123",
  "period": "2026-02",
  "total_spent_usd": "12.3456",
  "budget_limit_usd": "100.0000",
  "budget_remaining_usd": "87.6544",
  "runs": {
    "total": 150,
    "completed": 145,
    "failed": 5
  }
}
```

### 2.4 FORBIDDEN (Documentation Ban)
- ❌ `workspace_id` in request body (removed)
- ❌ `plan_id` in request body (removed, internal only)
- ❌ `run_id` in request body (server-generated, not client-provided)
- ❌ Synchronous 200 OK response (must be 202 + polling)

---

## 3. Idempotency (LOCK)

### 3.1 Idempotency-Key Header
- **Header**: `Idempotency-Key: <unique-string>`
- **Scope**: Per-tenant, per-key
- **TTL**: 7 days (duplicate detection window)
- **Behavior**:
  - Same `Idempotency-Key` within 7 days → 202 with existing `run_id` (no charge)
  - Same key after 7 days → treated as new request (billable)

### 3.2 Example
```bash
# First request
curl -X POST https://api.decisionproof.ai/v1/runs \
  -H "Authorization: Bearer sk_abc123_xyz789..." \
  -H "Idempotency-Key: request-20260217-001" \
  -d '{"pack_type": "decision", ...}'

# Response: 202 Accepted, run_id: run_abc123

# Duplicate request (within 7 days)
curl -X POST https://api.decisionproof.ai/v1/runs \
  -H "Authorization: Bearer sk_abc123_xyz789..." \
  -H "Idempotency-Key: request-20260217-001" \
  -d '{"pack_type": "decision", ...}'

# Response: 202 Accepted, run_id: run_abc123 (same), deduplication_status: "duplicate"
```

### 3.3 FORBIDDEN (Documentation Ban)
- ❌ `(workspace_id, run_id)` as idempotency scope (replaced by `Idempotency-Key`)

---

## 4. Error Responses (RFC 9457 Problem Details) (LOCK)

### 4.1 Standard Format
- **Media Type**: `application/problem+json`
- **Required Fields**:
  - `type` (string): URI reference for error type
  - `title` (string): Human-readable summary
  - `status` (integer): HTTP status code
  - `detail` (string): Detailed explanation
  - `instance` (string): URI reference for this occurrence

### 4.2 Extension Fields
- `reason_code` (string): Machine-readable error code (enum)
- `trace_id` (string): Distributed tracing ID

### 4.3 Example
```json
{
  "type": "https://docs.decisionproof.ai/errors/budget-exceeded",
  "title": "Budget Exceeded",
  "status": 402,
  "detail": "Requested max_cost_usd (0.0500) exceeds remaining budget (0.0200)",
  "instance": "/v1/runs",
  "reason_code": "BUDGET_EXCEEDED",
  "trace_id": "abc123-def456-789"
}
```

### 4.4 Common Error Codes
| Status | Reason Code | Description |
|--------|-------------|-------------|
| 401 | `AUTH_MISSING` | Missing `Authorization` header |
| 401 | `AUTH_INVALID` | Invalid token format or expired |
| 402 | `BUDGET_EXCEEDED` | Insufficient budget |
| 403 | `TENANT_MISMATCH` | Token does not own requested resource |
| 404 | `RUN_NOT_FOUND` | Run ID not found (or tenant mismatch) |
| 410 | `RUN_EXPIRED` | Run exceeded retention period |
| 422 | `INVALID_MONEY_SCALE` | `max_cost_usd` has >4 decimal places |
| 422 | `INVALID_PACK_TYPE` | Unknown `pack_type` |
| 429 | `RATE_LIMIT_EXCEEDED` | Too many requests |

---

## 5. Rate Limiting (LOCK)

### 5.1 Rate Limit Headers
**Response Headers** (all requests):
- `RateLimit-Limit: 100` - Total requests allowed in window
- `RateLimit-Remaining: 87` - Requests remaining
- `RateLimit-Reset: 1708156800` - Unix timestamp of next window reset

### 5.2 429 Too Many Requests
**Headers**:
- `Retry-After: 60` - Seconds until retry allowed
- `RateLimit-Limit: 100`
- `RateLimit-Remaining: 0`
- `RateLimit-Reset: 1708156800`

**Body** (RFC 9457):
```json
{
  "type": "https://docs.decisionproof.ai/errors/rate-limit-exceeded",
  "title": "Rate Limit Exceeded",
  "status": 429,
  "detail": "Request rate limit exceeded (100 req/min). Retry after 60 seconds.",
  "instance": "/v1/runs",
  "reason_code": "RATE_LIMIT_EXCEEDED",
  "trace_id": "abc123-def456-789"
}
```

### 5.3 Client Handling
```python
response = requests.post(url, headers=headers, json=body)

if response.status_code == 429:
    retry_after = int(response.headers.get("Retry-After", 60))
    time.sleep(retry_after)
    # Retry request
```

---

## 6. Tracing & Observability (LOCK)

### 6.1 Trace Context (W3C Trace Context)
**Request Header** (optional):
```http
traceparent: 00-4bf92f3577b34da6a3ce929d0e0e4736-00f067aa0ba902b7-01
```

**Response Header** (always present):
```http
X-Request-ID: req_abc123def456789
```

### 6.2 Trace Propagation
- Client sends `traceparent` → API passes to Worker → Worker passes to Reaper
- `trace_id` in `meta` field (request/response) links all operations
- `X-Request-ID` identifies specific API request (independent of `trace_id`)

### 6.3 Logging & Privacy
**Forbidden** (must NOT be logged):
- API keys / tokens (partial masking only: `sk_abc***`)
- Input data (PII risk)
- Result data (PII risk)

**Allowed**:
- `run_id`, `tenant_id`, `trace_id`, `request_id`
- `pack_type`, `status`, `money_state`
- Cost/budget values (USD amounts)
- Error codes and non-PII error details

---

## 7. Metering & Billing (LOCK)

### 7.1 Unit of Charge
- **Currency**: USD (United States Dollar)
- **Precision**: 4 decimal places (e.g., `"0.0050"` = half a cent)
- **Internal Storage**: USD micros (BIGINT, 1,000,000 micros = $1.00)

### 7.2 Charge Conditions
**Billable** (charges applied):
- `status: completed` - Successful execution
- `status: failed` with business logic errors (pack execution failure)

**Non-Billable** (no charge):
- `status: failed` with auth/validation errors (401, 403, 422)
- Duplicate requests (same `Idempotency-Key` within 7 days)

### 7.3 Cost Breakdown
```json
{
  "cost": {
    "reserved_usd": "0.0500",      // Max budget locked at submission
    "used_usd": "0.0120",           // Actual cost (execution + minimum fee)
    "minimum_fee_usd": "0.0010",    // Base fee per run
    "budget_remaining_usd": "99.9880"  // Tenant budget after settlement
  }
}
```

### 7.4 FORBIDDEN (Documentation Ban)
- ❌ "Decision Credits" (DC) terminology in customer-facing docs
- ❌ Credit/point-based pricing (use USD only)
- ❌ "Monthly DC quota" (use USD budget)

---

## 8. Retention & Data Lifecycle (LOCK)

### 8.1 Run Retention
- **Retention Period**: 45 days from creation
- **After Expiry**:
  - `GET /v1/runs/{run_id}` returns `410 Gone`
  - Result file (S3) deleted automatically (30-day lifecycle rule)

### 8.2 410 Gone Response
```json
{
  "type": "https://docs.decisionproof.ai/errors/run-expired",
  "title": "Run Expired",
  "status": 410,
  "detail": "Run run_abc123def456 exceeded 45-day retention period",
  "instance": "/v1/runs/run_abc123def456",
  "reason_code": "RUN_EXPIRED",
  "trace_id": "abc123-def456-789"
}
```

---

## 9. OpenAPI / Machine-Readable Specs (LOCK)

### 9.1 Security Scheme (openapi.json)
```json
{
  "components": {
    "securitySchemes": {
      "BearerAuth": {
        "type": "http",
        "scheme": "bearer",
        "bearerFormat": "sk_{key_id}_{secret}",
        "description": "Bearer token authentication. Format: sk_{key_id}_{secret} (e.g., sk_abc123_xyz789...)"
      }
    }
  }
}
```

**FORBIDDEN**:
- ❌ `sk_{environment}_{key_id}_{secret}` (no environment prefix)
- ❌ `X-API-Key` security scheme

### 9.2 Function Calling Specs (/docs/function-calling-specs.json)
- **Schema Source**: `RunCreateRequest` Pydantic model (apps/api/dpp_api/schemas.py)
- **Generation**: Auto-generated from model (no hardcoded schema)
- **Required Fields**: `pack_type`, `inputs`, `reservation`
- **Forbidden Fields**: `workspace_id`, `plan_id` (must NOT appear in schema)

---

## 10. Compliance & Change Control (LOCK)

### 10.1 Contract Change Process
1. Update this `SPEC_LOCK_PUBLIC_CONTRACT.md`
2. Update all documentation to match (public/docs, pilot, llms.txt)
3. Update machine-readable specs (function-calling-specs.json, OpenAPI)
4. Run regression tests (`test_docs_spec_lock.py`)
5. Increment version number (e.g., v0.4.2.2 → v0.4.3.0)

### 10.2 Forbidden Drift Detection
- **CI/CD Gate**: Automated test scans for forbidden tokens
- **Tokens**: `X-API-Key`, `dw_live_`, `dw_test_`, `sk_live_`, `sk_test_`, `workspace_id`, `plan_id`, `Decision Credits`
- **Scope**: `public/docs`, `docs/pilot`, `public/llms.txt`, `apps/api/dpp_api/main.py`

### 10.3 Version History
| Version | Date | Changes |
|---------|------|---------|
| v0.4.2.2 | 2026-02-17 | Initial SPEC LOCK: Bearer auth, async runs, RFC 9457, rate limits, no DC terminology |

---

**END OF SPEC LOCK**

This document is the **single source of truth** for public API contracts. All deviations must be approved and documented here first.
