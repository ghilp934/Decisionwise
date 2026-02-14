# Problem Types (RFC 9457)

Decisionproof uses [RFC 9457 Problem Details](https://www.rfc-editor.org/rfc/rfc9457.html) for structured error responses.

## Problem Details Format

All error responses use `application/problem+json` content type with standard fields:

```json
{
  "type": "https://api.decisionproof.ai/problems/rate-limit-exceeded",
  "title": "Rate Limit Exceeded",
  "status": 429,
  "detail": "Rate limit of 600 POST /runs per minute exceeded. Retry after 42 seconds.",
  "instance": "urn:decisionproof:trace:f47ac10b-58cc-4372-a567-0e02b2c3d479"
}
```

### Standard Fields

- **type**: URI identifying the problem type (machine-readable)
- **title**: Short, human-readable summary
- **status**: HTTP status code
- **detail**: Human-readable explanation specific to this occurrence
- **instance**: Opaque trace identifier in format `urn:decisionproof:trace:{uuid}` (NO path/DB PK leaks)

**IMPORTANT**: The `instance` field MUST use opaque identifiers. Never expose internal paths, database primary keys, or numeric-only values.

### Extension Fields

Decisionproof adds extension fields for specific problem types:

- **violated-policies**: Array of policy violations (rate-limit-exceeded)
- **retry_after**: Seconds to wait before retry (rate-limit-exceeded)

## Decisionproof Problem Types

All Decisionproof problem types use the base URI: `https://api.decisionproof.ai/problems/`

### Authentication & Authorization

#### http-401 (Unauthorized)

**Type**: `https://api.decisionproof.ai/problems/http-401`

**When**: Missing or invalid authentication credentials.

**Client Action**: Verify Bearer token is correct and included in `Authorization` header. Check token format: `sk_{environment}_{key_id}_{secret}`.

**Example**:
```json
{
  "type": "https://api.decisionproof.ai/problems/http-401",
  "title": "Unauthorized",
  "status": 401,
  "detail": "Missing or invalid authentication credentials",
  "instance": "urn:decisionproof:trace:a1b2c3d4-e5f6-7890-abcd-ef1234567890"
}
```

---

#### http-403 (Forbidden)

**Type**: `https://api.decisionproof.ai/problems/http-403`

**When**: Valid authentication but lacks permission for requested resource.

**Client Action**: Check tenant access permissions. Verify API key scope.

---

### Plan Enforcement

#### no-active-plan (400)

**Type**: `https://api.decisionproof.ai/problems/no-active-plan`

**When**: Tenant has no active plan assigned.

**Client Action**: Contact billing to activate a plan.

---

#### pack-type-not-allowed (400)

**Type**: `https://api.decisionproof.ai/problems/pack-type-not-allowed`

**When**: Requested pack type is not allowed in tenant's plan.

**Client Action**: Upgrade plan or use allowed pack type.

**Example**:
```json
{
  "type": "https://api.decisionproof.ai/problems/pack-type-not-allowed",
  "title": "Pack Type Not Allowed",
  "status": 400,
  "detail": "Pack type 'enterprise' is not allowed in plan 'STARTER'. Allowed types: ['pilot', 'basic']",
  "instance": "urn:decisionproof:trace:b2c3d4e5-f6a7-8901-bcde-f2345678901a"
}
```

---

#### max-cost-too-low (400)

**Type**: `https://api.decisionproof.ai/problems/max-cost-too-low`

**When**: Requested max_cost is below minimum threshold ($0.005).

**Client Action**: Increase max_cost to at least $0.005 (5000 micros).

---

#### max-cost-exceeded (402)

**Type**: `https://api.decisionproof.ai/problems/max-cost-exceeded`

**When**: Requested max_cost exceeds plan limit for pack type.

**Client Action**: Reduce max_cost or upgrade plan.

**Example**:
```json
{
  "type": "https://api.decisionproof.ai/problems/max-cost-exceeded",
  "title": "Maximum Cost Exceeded",
  "status": 402,
  "detail": "Requested max_cost (50000 micros) exceeds plan limit (10000 micros) for pack_type 'pilot'",
  "instance": "urn:decisionproof:trace:c3d4e5f6-a7b8-9012-cdef-345678901abc"
}
```

---

### Rate Limiting

#### rate-limit-exceeded (429)

**Type**: `https://api.decisionproof.ai/problems/rate-limit-exceeded`

**When**: Request rate limit exceeded (POST /runs or GET /runs polling).

**Headers**:
- `Retry-After`: Seconds to wait before retry (REQUIRED)
- `RateLimit-Policy`: Policy name, window, quota
- `RateLimit`: Remaining requests, TTL

**Client Action**: Wait for `Retry-After` seconds, then retry. Implement exponential backoff for repeated 429s.

**Example**:
```json
{
  "type": "https://api.decisionproof.ai/problems/rate-limit-exceeded",
  "title": "Rate Limit Exceeded",
  "status": 429,
  "detail": "Rate limit of 600 POST /runs per minute exceeded. Retry after 42 seconds.",
  "instance": "urn:decisionproof:trace:d4e5f6a7-b8c9-0123-def0-45678901abcd"
}
```

See [Rate Limits](/docs/rate-limits.md) for details on IETF RateLimit headers.

---

### Validation Errors

#### validation-error (422)

**Type**: `https://api.decisionproof.ai/problems/validation-error`

**When**: Request validation failed (Pydantic/FastAPI validation).

**Client Action**: Fix request payload per OpenAPI schema. Check `detail` field for specific field error.

**Example**:
```json
{
  "type": "https://api.decisionproof.ai/problems/validation-error",
  "title": "Request Validation Failed",
  "status": 422,
  "detail": "Invalid field 'body.workspace_id': Field required",
  "instance": "urn:decisionproof:trace:e5f6a7b8-c9d0-1234-ef01-5678901abcde"
}
```

**IMPORTANT**: 422 errors are **billable** (valid request format, invalid business logic). All other 4xx/5xx errors are non-billable.

---

#### invalid-date-format (400)

**Type**: `https://api.decisionproof.ai/problems/invalid-date-format`

**When**: Date parameter not in YYYY-MM-DD format.

**Client Action**: Use ISO 8601 date format (YYYY-MM-DD).

---

#### invalid-date-range (400)

**Type**: `https://api.decisionproof.ai/problems/invalid-date-range`

**When**: Date range validation failed (from_date > to_date).

**Client Action**: Ensure from_date <= to_date.

---

### Generic HTTP Errors

#### http-{status_code}

**Type**: `https://api.decisionproof.ai/problems/http-{status_code}`

**When**: Generic HTTP error not covered by specific problem types.

**Examples**:
- `http-404`: Resource not found
- `http-409`: Idempotency key conflict (different payload)

---

#### internal-error (500)

**Type**: `https://api.decisionproof.ai/problems/internal-error`

**When**: Unexpected server error.

**Client Action**: Retry with exponential backoff. Contact support if persists.

---

## IANA Standard Problem Types

Decisionproof also uses IANA standard problem types where applicable:

- `https://iana.org/assignments/http-problem-types#quota-exceeded` (429)
- `https://iana.org/assignments/http-problem-types#unprocessable-entity` (422)

---

## Billability

All Problem Details responses (4xx, 5xx) are **non-billable** except:

- **422 Unprocessable Entity**: Billable (valid request format, invalid business logic)

See [Metering & Billing](/docs/metering-billing.md) for complete rules.

---

## Security: Opaque Instance Identifiers

**CRITICAL**: The `instance` field MUST NEVER expose:
- Internal paths (e.g., `/v1/runs/123`)
- Database primary keys (e.g., numeric-only values)
- Internal identifiers

**Correct format**: `urn:decisionproof:trace:{uuid}`

**Example**:
```json
{
  "instance": "urn:decisionproof:trace:f47ac10b-58cc-4372-a567-0e02b2c3d479"
}
```

**Invalid examples**:
```json
{
  "instance": "/v1/runs/123",  // ❌ PATH LEAK
  "instance": "12345",          // ❌ DB PK LEAK
  "instance": "urn:decisionproof:trace:123"  // ❌ NUMERIC-ONLY
}
```

---

## Client Error Handling

1. **Parse Content-Type**: Ensure `application/problem+json`
2. **Read type field**: Identify problem type for machine-readable handling
3. **Read detail field**: Extract human-readable error message
4. **For 429**: Check `Retry-After` header, wait, then retry
5. **Log instance field**: Include opaque trace ID in support requests

See [OpenAPI Spec](/.well-known/openapi.json) for complete error schemas.
