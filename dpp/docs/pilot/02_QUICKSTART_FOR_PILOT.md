# Quickstart for Pilot

**Decisionproof API - 빠른 시작 가이드 (Staging 전용)**

---

## 기본 정보

**Base URL (Staging):**
```
https://staging-api.decisionproof.ai
```

**인증 방식:**
- Bearer Token (API Key)
- Header: `Authorization: Bearer sk_staging_...`

**근거:**
- apps/api/dpp_api/main.py (lines 28-40: FastAPI app setup)
- apps/api/dpp_api/routers/health.py (health endpoints)
- README.md (API Key authentication SHA-256 hashed)

---

## 주요 엔드포인트

### 1. Health Check (인증 불필요)

```bash
# Basic liveness check
curl https://staging-api.decisionproof.ai/health

# Response:
{
  "status": "healthy",
  "version": "0.4.2.2",
  "services": {
    "api": "up",
    "database": "up",
    "redis": "up",
    "s3": "up",
    "sqs": "up"
  }
}
```

**근거:** apps/api/dpp_api/routers/health.py (lines 105-123)

### 2. Readiness Check (인증 불필요)

```bash
# Dependency health check
curl https://staging-api.decisionproof.ai/readyz

# Response (all up):
{
  "status": "ready",
  "version": "0.4.2.2",
  "services": {...}
}

# Response (some down): 503 Service Unavailable
{
  "status": "not_ready",
  "services": {"database": "down: connection refused"}
}
```

**근거:** apps/api/dpp_api/routers/health.py (lines 126-158)

### 3. OpenAPI Specification (인증 불필요)

```bash
curl https://staging-api.decisionproof.ai/.well-known/openapi.json | jq '.info'

# Response:
{
  "title": "Decisionproof API",
  "description": "Agent-centric decision execution platform...",
  "version": "0.4.2.2"
}
```

**근거:** apps/api/dpp_api/main.py (lines 32-33: openapi_version="3.1.0")

### 4. API Documentation (인증 불필요)

```bash
# Swagger UI
open https://staging-api.decisionproof.ai/api-docs

# ReDoc
open https://staging-api.decisionproof.ai/redoc
```

**근거:** apps/api/dpp_api/main.py (lines 32-33: docs_url="/api-docs", redoc_url="/redoc")

### 5. Pricing SSOT (인증 불필요)

```bash
curl https://staging-api.decisionproof.ai/pricing/ssot.json | jq '.tiers[] | select(.tier=="STARTER")'

# Response:
{
  "tier": "STARTER",
  "monthly_base_price": 29000,
  "included_dc_per_month": 1000,
  "overage_price_per_dc": 39,
  "limits": {
    "rate_limit_rpm": 60,
    "monthly_quota_dc": 1000,
    ...
  }
}
```

**근거:** apps/api/dpp_api/pricing/fixtures/pricing_ssot.json (lines 94-100)

### 6. List Runs (인증 필요)

```bash
export DPP_STAGING_TOKEN="sk_staging_..."

curl -H "Authorization: Bearer $DPP_STAGING_TOKEN" \
  https://staging-api.decisionproof.ai/v1/runs

# Response (200 OK):
{
  "runs": []
}

# Response (401 Unauthorized - 토큰 없음 또는 잘못됨):
{
  "type": "https://iana.org/assignments/http-problem-types#unauthorized",
  "title": "Unauthorized",
  "status": 401,
  "detail": "Missing or invalid API key"
}
```

**근거:** apps/api/dpp_api/main.py (rate_limit_middleware checks Authorization header)

### 7. Create Run (인증 필요)

```bash
curl -X POST \
  -H "Authorization: Bearer $DPP_STAGING_TOKEN" \
  -H "Content-Type: application/json" \
  -H "Idempotency-Key: $(uuidgen)" \
  -d '{
    "pack_type": "decision",
    "input": {
      "question": "Should we proceed with feature X?",
      "context": "..."
    }
  }' \
  https://staging-api.decisionproof.ai/v1/runs

# Response (201 Created):
{
  "run_id": "run_abc123...",
  "status": "queued",
  "created_at": "2026-02-15T12:34:56Z",
  ...
}
```

---

## Rate Limit 헤더

모든 `/v1/*` 엔드포인트는 Rate Limit 헤더를 반환합니다:

```bash
curl -v -H "Authorization: Bearer $DPP_STAGING_TOKEN" \
  https://staging-api.decisionproof.ai/v1/runs

# Response Headers:
RateLimit-Policy: "default"; q=60; w=60
RateLimit: "default"; r=58; t=42
```

**해석:**
- `q=60`: Quota (60 requests)
- `w=60`: Window (60 seconds)
- `r=58`: Remaining (58 requests 남음)
- `t=42`: Time until reset (42 seconds)

**근거:** apps/api/dpp_api/main.py (lines 116-150: rate_limit_middleware)

---

## 오류 응답 (RFC 9457)

모든 오류는 RFC 9457 Problem Details 형식으로 반환됩니다:

```bash
# Example: 429 Too Many Requests
curl -H "Authorization: Bearer $DPP_STAGING_TOKEN" \
  https://staging-api.decisionproof.ai/v1/runs

# Response (429):
{
  "type": "https://iana.org/assignments/http-problem-types#quota-exceeded",
  "title": "Too Many Requests",
  "status": 429,
  "detail": "Rate limit exceeded: 60 requests per minute",
  "instance": "/v1/runs",
  "request_id": "req_xyz789..."
}
```

**근거:** apps/api/dpp_api/pricing/fixtures/pricing_ssot.json (lines 40-46: problem_details)

---

## 다음 단계

1. 위 예시로 각 엔드포인트 호출 성공 확인
2. Idempotency-Key 사용법 숙지 (중복 요청 방지)
3. Rate Limit 준수 (60 RPM)
4. 오류 발생 시 `request_id` 기록 및 지원팀 제출
