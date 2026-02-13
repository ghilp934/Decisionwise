# DPP (Decision Pack Platform) v0.4.2.2 — 상세 개발명세 (Claude Code Implementation Spec)
Version: v0.4.2.2  
As-of: 2026-02-13 (Asia/Seoul)  
Document type: Implementation-grade spec (API + Worker + Reaper + Budget + Storage + Queue)  
Source of truth (policy/locks): `DPP_v0_4_2_2_Report_Rebuild_Integrated_20260213.md`

---

## 0) 10초 스펙 잠금 (Non-negotiables)

### 0.1 Determinism Locks (DEC Cards)
- DEC-4201 Persistence: S3-Compatible Object Storage + 30일 Lifecycle + DB pointer
- DEC-4202 Idempotency: Idempotency-Key + Lock-on-Key + payload_hash mismatch=409
- DEC-4203 Reserve-then-Settle: Submit reserve, Complete settle, Fail/Timeout minimum_fee
- DEC-4204 AuthZ: owner guard + stealth 404 + run_id UUID
- DEC-4205 Zombie: lease TTL + Reaper 강제 종료/정산
- DEC-4206 Termination Atomic Commit: cross-system “atomic-ish” + reconcile
- DEC-4207 Polling Abuse: GET rate limit/quota, 429 Retry-After
- DEC-4208 Cost Headers: X-DPP-* 표준화
- DEC-4209 Retention: 30일 이후 owner=410, non-owner=404
- DEC-4210 Optimistic Locking: `runs.version` DB-CAS로 Worker/Reaper 경쟁 차단
- DEC-4211 Money Type: 내부 돈/비용은 `USD_MICROS (BIGINT)`로만 저장/계산
- DEC-4212 Queue: SQS-Compatible(Prod) + LocalStack(Dev)

### 0.2 핵심 상수(고정)
- retention_days = 30
- presigned_url_ttl_seconds_default = 600 (10분)
- lease_ttl_seconds = 120
- lease_heartbeat_interval_seconds = 30
- reaper_interval_seconds = 30
- idem_lock_ttl_seconds = 5
- idempotency_mapping_ttl_seconds = retention_days * 86400 (기본 30일)
- reservation_ttl_seconds = 3600 (1시간)
- poll_recommended_interval_ms = 1500
- timebox_sec_default = 90 (max 90)
- minimum_fee_usd = max(0.005, 0.02 * reserved_usd), cap <= 0.10
- status machine:
  - Execution: QUEUED, PROCESSING, COMPLETED, FAILED, EXPIRED
  - Money: NONE, RESERVED, SETTLED, REFUNDED, DISPUTED

---

## 1) 목표/범위

### 1.1 목표(이 문서가 만들어낼 구현 결과)
- “Run”을 submit → reserve → queue → execute → persist result → settle/refund → poll로 조회 가능한 end-to-end 파이프라인을 구현한다.
- Worker/Reaper 경쟁 상황에서도 **정확히 1회만 terminal 전이**가 커밋되도록 한다(DEC-4210).
- 비용/예산은 내부적으로 **정수 micros ledger**로만 처리해 부동소수 오차를 제거한다(DEC-4211).

### 1.2 Non-goals (v0.4.2.2에서 하지 않음)
- 결제(카드/PG), 환율, 세금계산서 등 외부 금융 연동
- UI/웹프론트
- 고급 RBAC/SSO (API Key 기반 단일 테넌트 auth만)
- 장기 아카이빙(Glacier tiering) 최적화

---

## 2) 기준 기술 스택(권장/잠금)

> 구현은 **Python + FastAPI + PostgreSQL + Redis + S3 + SQS**를 기준으로 한다.

- Language: Python 3.12+
- API: FastAPI + Pydantic v2
- DB: PostgreSQL 15+
- ORM/Migration: SQLAlchemy 2 + Alembic
- Redis: Redis 7+
- Object Storage: AWS S3 (또는 S3-compatible)
- Queue: AWS SQS Standard (Dev: LocalStack SQS)
- AWS SDK: boto3
- Observability: JSON structured logging (structlog or stdlib)
- Testing: pytest + httpx + (docker-compose or testcontainers)
- Lint/Type: ruff + mypy (또는 pyright)

---

## 3) 레포 구조(Claude Code가 바로 만들 수 있게 고정)

```
dpp/
  apps/
    api/                # FastAPI
      dpp_api/
        main.py
        deps.py
        routers/
          runs.py
          health.py
        auth/
          api_key.py
        budget/
          redis_scripts.py
          budget_manager.py
        storage/
          s3_client.py
        queue/
          sqs_client.py
        db/
          session.py
          models.py
          repo_runs.py
        utils/
          money.py
          hashing.py
          problem_details.py
          time.py
      tests/
        unit/
        integration/
    worker/
      dpp_worker/
        main.py
        executor/
          base.py
          stub_decision.py
        loops/
          sqs_loop.py
        finalize/
          optimistic_commit.py
      tests/
    reaper/
      dpp_reaper/
        main.py
        loops/
          reaper_loop.py
        finalize/
          optimistic_commit.py
      tests/
  infra/
    docker-compose.yml
    localstack-init/
      init.sh
  alembic/
    versions/
  pyproject.toml
  README.md
  CLAUDE.md
  .claude/settings.json
```

---

## 4) 시스템 아키텍처

### 4.1 컴포넌트
1) API Service (Authoritative)
- 인증/인가(Auth/AuthZ)
- budget reserve/settle 호출(BudgetManager)
- RunRecord 생성/상태 전이(DB-CAS)
- SQS enqueue
- GET polling + presigned URL 생성

2) Worker Service
- SQS receive
- QUEUED → PROCESSING DB-CAS (lease 발급)
- Pack 실행(timebox)
- 결과를 S3에 저장 + sha256
- **최종 종료(terminal) DB-CAS 승리한 1개 주체만** settle + 결과 포인터 반영

3) Reaper Service
- 주기적으로 PROCESSING 중 lease 만료 run을 탐지
- **DB-CAS로 종료권(terminal claim) 획득** 후 실패 처리 + minimum_fee settle

4) BudgetManager (Redis Lua)
- reserve / settle / refund 를 Redis Lua로 원자 실행
- 모든 금액은 `*_usd_micros`로 처리

5) Object Storage (S3)
- 결과물 envelope 및 artifact 저장
- Lifecycle rule로 30일 만료 + multipart abort 7일

6) Queue (SQS)
- 메시지: `{ "run_id": "<uuid>", "pack_type": "...", "tenant_id": "...", "enqueued_at": "..." }`

---

## 5) 데이터 모델 (PostgreSQL)

### 5.1 테이블 목록(최소)
- `tenants`
- `api_keys`
- `runs`

### 5.2 DDL (권장; Alembic으로 구현)

#### 5.2.1 tenants
```sql
CREATE TABLE tenants (
  tenant_id TEXT PRIMARY KEY,
  display_name TEXT NOT NULL,
  status TEXT NOT NULL DEFAULT 'ACTIVE',
  created_at TIMESTAMPTZ NOT NULL DEFAULT now()
);
```

#### 5.2.2 api_keys
- API Key는 평문 저장 금지(해시 저장).
```sql
CREATE TABLE api_keys (
  key_id UUID PRIMARY KEY,
  tenant_id TEXT NOT NULL REFERENCES tenants(tenant_id),
  key_hash TEXT NOT NULL,
  label TEXT,
  status TEXT NOT NULL DEFAULT 'ACTIVE',
  created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
  last_used_at TIMESTAMPTZ
);
CREATE INDEX idx_api_keys_tenant ON api_keys(tenant_id);
```

#### 5.2.3 runs (authoritative)
```sql
CREATE TABLE runs (
  run_id UUID PRIMARY KEY,
  tenant_id TEXT NOT NULL REFERENCES tenants(tenant_id),

  pack_type TEXT NOT NULL,
  profile_version TEXT NOT NULL DEFAULT 'v0.4.2.2',

  status TEXT NOT NULL,                    -- QUEUED/PROCESSING/COMPLETED/FAILED/EXPIRED
  money_state TEXT NOT NULL,               -- NONE/RESERVED/SETTLED/REFUNDED/DISPUTED

  idempotency_key TEXT,
  payload_hash TEXT NOT NULL,

  version BIGINT NOT NULL DEFAULT 0,       -- DEC-4210

  reservation_max_cost_usd_micros BIGINT NOT NULL,
  actual_cost_usd_micros BIGINT,
  minimum_fee_usd_micros BIGINT NOT NULL,

  result_bucket TEXT,
  result_key TEXT,
  result_sha256 TEXT,
  retention_until TIMESTAMPTZ NOT NULL,

  lease_token TEXT,
  lease_expires_at TIMESTAMPTZ,

  -- (권장) 2단계 finalize를 명확히 하기 위한 내부 토큰(외부 API 영향 없음)
  finalize_token TEXT,
  finalize_stage TEXT,                     -- NULL | CLAIMED | COMMITTED
  finalize_claimed_at TIMESTAMPTZ,

  last_error_reason_code TEXT,
  last_error_detail TEXT,

  trace_id TEXT,

  created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
  updated_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE INDEX idx_runs_tenant_created ON runs(tenant_id, created_at DESC);
CREATE INDEX idx_runs_status_lease ON runs(status, lease_expires_at);
CREATE INDEX idx_runs_idem ON runs(tenant_id, idempotency_key);
```

##### 앱 레벨 불변식(테스트로 강제)
- `actual_cost_usd_micros <= reservation_max_cost_usd_micros`
- terminal status(COMPLETED/FAILED/EXPIRED)라면 `money_state in (SETTLED, REFUNDED)`

---

## 6) Redis Keyspace & Lua Scripts

### 6.1 Key naming (잠금)
- `budget:{tenant_id}:balance_usd_micros` (string int)
- `reserve:{run_id}` (hash: reserved_usd_micros, tenant_id, created_at_ms) TTL=3600s
- `idem:{tenant_id}:{idempotency_key}` (hash: run_id, payload_hash, created_at_ms) TTL=30d
- `idem_lock:{tenant_id}:{idempotency_key}` (string) TTL=5s
- `lease:{run_id}` (string lease_token) TTL=120s

### 6.2 Reserve.lua (정확한 구현 스펙)
- KEYS[1]=budget_key
- KEYS[2]=reserve_key
- ARGV[1]=tenant_id
- ARGV[2]=reserved_usd_micros (int string)
- ARGV[3]=created_at_ms

Return codes
- `OK <new_balance>`
- `ERR_INSUFFICIENT <balance>`
- `ERR_ALREADY_RESERVED`

Reference implementation (Lua)
```lua
local budget_key = KEYS[1]
local reserve_key = KEYS[2]
local tenant_id = ARGV[1]
local reserved = tonumber(ARGV[2])
local created_at_ms = ARGV[3]

if redis.call("EXISTS", reserve_key) == 1 then
  return { "ERR_ALREADY_RESERVED" }
end

local bal = tonumber(redis.call("GET", budget_key) or "0")
if bal < reserved then
  return { "ERR_INSUFFICIENT", tostring(bal) }
end

redis.call("SET", budget_key, tostring(bal - reserved))
redis.call("HSET", reserve_key,
  "tenant_id", tenant_id,
  "reserved_usd_micros", tostring(reserved),
  "created_at_ms", created_at_ms
)
return { "OK", tostring(bal - reserved) }
```

NOTE:
- Reserve.lua는 reserve_key를 생성만 한다. 호출자는 OK 반환 후 `EXPIRE reserve_key 3600`을 즉시 수행해 TTL을 보장한다.


### 6.3 Settle.lua (정확한 구현 스펙)
- KEYS[1]=budget_key
- KEYS[2]=reserve_key
- ARGV[1]=charge_usd_micros (int string)  # success=actual_cost, fail/timeout=minimum_fee
Return codes
- `OK <charge> <refund> <new_balance>`
- `ERR_NO_RESERVE`

```lua
local budget_key = KEYS[1]
local reserve_key = KEYS[2]
local charge = tonumber(ARGV[1])

if redis.call("EXISTS", reserve_key) ~= 1 then
  return { "ERR_NO_RESERVE" }
end

local reserved = tonumber(redis.call("HGET", reserve_key, "reserved_usd_micros") or "0")
if charge > reserved then
  charge = reserved
end
local refund = reserved - charge

local bal = tonumber(redis.call("GET", budget_key) or "0")
bal = bal + refund
redis.call("SET", budget_key, tostring(bal))
redis.call("DEL", reserve_key)
return { "OK", tostring(charge), tostring(refund), tostring(bal) }
```

### 6.4 RefundFull.lua
- KEYS[1]=budget_key
- KEYS[2]=reserve_key
Return codes
- `OK <refund> <new_balance>`
- `ERR_NO_RESERVE`

---

## 7) HTTP API (FastAPI)

### 7.1 공통
- Auth: `Authorization: Bearer <api_key>`
- Content-Type: `application/json`
- Error: RFC 9457 Problem Details (`application/problem+json`)
- Trace header: `X-Trace-Id` (optional; 없으면 서버 생성)

Problem Details 필드(잠금)
- `type` (uri)
- `title`
- `status`
- `detail`
- `instance` (request path)
- extensions:
  - `reason_code` (enum)
  - `trace_id`
  - `run_id` (가능할 때)

### 7.2 POST /v1/runs
Headers
- `Idempotency-Key` required (8~64 chars; tenant scope)

Body (RunCreateRequest)
- `pack_type` (enum: ocr, url, decision, compliance, eval)
- `inputs` (object; pack별 스키마)
- `reservation`
  - `max_cost_usd` (4dp decimal string)
  - `timebox_sec` (1~90; default 90)
  - `min_reliability_score` (0.0~1.0; default 0.8)
- `options` (optional)
  - `inline` (0/1; default 0)  # inline=1이면 result 일부를 body에 포함(256KB 제한)
- `meta` (optional)
  - `trace_id` (optional)
  - `profile_version` (optional; default PROFILE_DPP_0_4_2_2)

Response 202 (RunReceipt)
- `run_id`
- `status`=QUEUED
- `reservation`
  - `max_cost_usd`
  - `timebox_sec`
  - `min_reliability_score`
- `poll`
  - `href`: `/v1/runs/{run_id}`
  - `recommended_interval_ms`: 1500
- `meta`
  - `trace_id`
  - `profile_version`

Idempotency
- same key + same hash => return existing receipt (202)
- same key + diff hash => 409 IDEMPOTENCY_CONFLICT

Errors
- 401 AUTH_INVALID
- 402 BUDGET_DRAINED
- 409 IDEMPOTENCY_CONFLICT
- 429 RATE_LIMITED

### 7.3 GET /v1/runs/{run_id}
Behavior
- owner guard 실패 포함해 404 stealth
- retention 만료: owner 410, non-owner 404

Response 200
- `run_id, status, money_state`
- `cost`: reserved/used/minimum_fee/budget_remaining (4dp)
- `result`:
  - COMPLETED: `presigned_url`, `sha256`, `expires_at`
  - FAILED: `problem` 또는 `reason_code`
- `meta`: created_at, updated_at, trace_id

---
## 7.4 X-DPP Cost Headers (DEC-4208)

API는 POST/GET 모두에서 다음 헤더를 **항상** 포함한다(값이 없으면 "0.0000"로 반환).
- `X-DPP-Cost-Reserved`: reserved_usd (4dp)
- `X-DPP-Cost-Used`: used_usd (4dp; COMPLETED/FAILED 이후 actual/min_fee)
- `X-DPP-Budget-Remaining`: budget_remaining_usd (4dp)
- `X-DPP-Tokens-Consumed`: (옵션) pack별 토큰/리소스 소비량(없으면 "0")

> body의 cost 필드와 헤더 값은 **항상 동일해야** 한다.

---


## 8) Queue Contract (SQS)

### 8.1 Queue 설정(권장)
- Standard queue
- VisibilityTimeout: 120s (lease_ttl과 정렬)
- DLQ: maxReceiveCount=3

### 8.2 Message schema
```json
{
  "run_id": "uuid",
  "tenant_id": "t_...",
  "pack_type": "ocr",
  "enqueued_at": "2026-02-13T00:00:00Z",
  "schema_version": "1"
}
```

---

## 9) Worker 상세 (DEC-4210/4206 중심)

### 9.1 Worker loop
1) SQS ReceiveMessage (long polling)
2) run 조회 (DB)
3) QUEUED → PROCESSING DB-CAS
   - 조건: status='QUEUED' AND version=:v
   - 업데이트: status='PROCESSING', lease_token, lease_expires_at=now+120s, version=v+1
   - 실패(0 rows): 이미 처리됨 → ack & skip
4) Redis lease:{run_id} SETNX TTL=120
5) Pack execute(timebox)
6) 결과 envelope 생성 + S3 업로드 + sha256
7) Terminal finalize (2단계)
   - (A) claim:
     - 조건: status='PROCESSING' AND version=:v AND lease_token=:lease_token AND finalize_stage IS NULL
     - 업데이트: finalize_token=:uuid, finalize_stage='CLAIMED', finalize_claimed_at=now, version=v+1
     - 실패(0 rows): loser → settle 금지 / 결과 포인터 commit 금지 / ack
   - (B) side-effects (winner only):
     - settle: charge = min(actual_cost, reserved)
     - DB final commit:
       - 조건: run_id=:id AND version=:v_claimed AND finalize_token=:token AND finalize_stage='CLAIMED'
       - 업데이트:
         - status='COMPLETED'
         - money_state='SETTLED'
         - actual_cost_usd_micros=:charge
         - result_bucket/key/sha256
         - finalize_stage='COMMITTED'
         - version=v_claimed+1
8) ack

### 9.2 Pack Executor
- 최소 구현: `decision` stub executor
  - pack_envelope.json 생성(간단 content)
  - actual_cost_usd_micros = min(50_000, reservation_max_cost_usd_micros)  # 예: $0.05

### 9.3 Pack Envelope (S3 저장 포맷 잠금)

Worker는 결과를 항상 **envelope JSON**으로 저장한다.
- 파일명: `pack_envelope.json`
- Content-Type: `application/json; charset=utf-8`
- 크기 제한(권장): 1MB 이내 (초과 시 artifact로 분리)

Envelope schema (권장)
```json
{
  "schema_version": "0.4.2.2",
  "run_id": "uuid",
  "pack_type": "url|ocr|decision|compliance|eval",
  "status": "COMPLETED|FAILED",
  "generated_at": "ISO-8601",
  "cost": {
    "reserved_usd": "0.2500",
    "used_usd": "0.0500",
    "minimum_fee_usd": "0.0050"
  },
  "data": {},
  "artifacts": {},
  "logs": {
    "discard_log": [],
    "blocked_log": []
  },
  "meta": {
    "trace_id": "t_...",
    "profile_version": "PROFILE_DPP_0_4_2_2"
  }
}
```

### 9.4 Pack 구현 상세 (v0.4.2.2 최소)

> 플랫폼 코어(MS0~MS5) 구현 이후, pack별 구현은 아래 순서로 진행한다.

#### 9.4.1 DecisionPack (최소 필수)
- 입력: `inputs = { "question": str, "context": str?, "mode": "brief|full"? }`
- 출력(data):
  - `answer_text` (string)
  - `confidence` (0~1 float; 표시용, 내부 돈 계산에 사용 금지)
- tokens_consumed (옵션): LLM을 붙이기 전까지는 0으로 고정 가능.

#### 9.4.2 URLPack (SmartFetcher 포함; 보안 필수)
- 입력(권장; MCP 스키마와 정렬)
```json
{
  "urls": ["https://..."],
  "max_urls": 30,
  "fetch_timeout_sec": 10,
  "max_redirect_hops": 5,
  "block_private_ip": true,
  "allow_https_only": true
}
```
- 핵심 규칙(잠금):
  - HTTPS만 허용(옵션 allow_http=false 기본)
  - SSRF 방지: private/loopback/link-local/multicast/reserved IP 차단
  - 리다이렉트는 **수동 추적** + hop cap(<=5), 매 hop마다 DNS 재해석 + IP 재검증
  - 응답 바디 최대 크기 cap(예: 2MB), 초과 시 TRUNCATED 표시
  - robots.txt 준수는 v0.4.2.2에서 Non-goal(단, 합법/정책 위반 우회 금지)

- 출력(data):
  - `results`: [{ url, final_url, status_code, content_type, title?, text_excerpt?, fetched_at }]
- 출력(logs):
  - discard_log: [{ url, reason }]  # 예: TIMEOUT, NON_HTTPS, TOO_MANY_REDIRECTS, CONTENT_TOO_LARGE
  - blocked_log: [{ url, resolved_ip, reason }]  # 예: PRIVATE_IP, LOOPBACK

#### 9.4.3 OCRPack (스켈레톤; 파이프라인만 명세)
- 입력(권장)
```json
{
  "images": [
    { "kind": "s3", "bucket": "...", "key": "..." }
  ],
  "ocr_profile": "P1|P2A|P2B|P3",
  "language": "kor+eng",
  "max_pages": 50
}
```
- 파이프라인(잠금 요약; 상세는 OCR 앱 베스트프랙티스 문서 준수):
  - Preflight(layout sniff) → PSM lock → (필요 시) 전처리 → OCR pass(타이틀/본문/미세문구)
  - Output은 누락 방지 우선: 판독 불가 구간은 [□]/(?)로 기록
- 출력(data):
  - `texts`: [{ source, page?, blocks:[{text, confidence?}] }]
  - `notes`: [{ type:"VERIFY_SPELLING", value:"..." }]


---

## 10) Reaper 상세

### 10.1 scan
- status='PROCESSING' AND lease_expires_at < now()

### 10.2 reaper finalize (winner-only)
- claim:
  - 조건: status='PROCESSING' AND version=:v AND lease_expires_at < now() AND finalize_stage IS NULL
  - 업데이트: finalize_token=:uuid, finalize_stage='CLAIMED', finalize_claimed_at=now, version=v+1
- settle: charge=min(minimum_fee, reserved)
- final commit:
  - status='FAILED'
  - money_state='SETTLED'
  - actual_cost_usd_micros=:charge
  - last_error_reason_code='WORKER_TIMEOUT'
  - finalize_stage='COMMITTED'
  - version+1

---

## 11) Idempotency (Lock-on-Key)

### 11.1 payload_hash
- canonical JSON(키 정렬, 공백 제거) 후 SHA-256
- 제외: client.trace_id/client_version 등
- 포함: pack_type/inputs/timebox_sec/max_cost_usd/artifacts

### 11.2 POST 알고리즘(잠금)
1) payload_hash 계산
2) SETNX idem_lock TTL=5s
3) lock을 얻지 못한 경우:
   - idem mapping 조회
   - mapping 존재(=이미 처리 시작됨)면 기존 RunReceipt(202) 반환
   - mapping 부재면 409 또는 503 (권장: 409 + client retry)
4) idem mapping 존재:
   - hash 동일: 기존 RunReceipt(202) 반환
   - hash 다름: 409 IDEMPOTENCY_CONFLICT
5) reserve (Reserve.lua) 실행 + reserve_key TTL=3600s 설정
6) runs row insert (status=QUEUED, money_state=RESERVED)
7) idem mapping set(TTL=30d)
8) enqueue SQS
9) enqueue 실패:
   - refund_full (RefundFull.lua)
   - run FAILED/REFUNDED (CAS)
   - 503 Problem Details(reason_code=QUEUE_ENQUEUE_FAILED)

추가: Reservation TTL Sweeper (권장; 1~5분)
- 대상: status=QUEUED AND created_at < now()-3600s
- 동작: DB-CAS claim 후 refund_full + status=FAILED(reason_code=RESERVATION_EXPIRED) + money_state=REFUNDED
 비용/돈 처리 (USD_MICROS)

### 12.1 변환 규칙(잠금)
- 입력 `max_cost_usd`는 4dp decimal string만 허용
- micros = int(decimal * 1_000_000) with exact decimal (Python Decimal 사용)
- 응답 표시: 4dp string

### 12.2 최소 수수료 계산(잠금)
- reserved_usd_micros = reservation_max_cost_usd_micros
- min_fee_usd_micros = min(
    max(5_000, floor(reserved_usd_micros * 0.02)),
    100_000
  )

---

## 13) Object Storage (S3)

### 13.1 Key naming
- bucket: `dpp-results`
- prefix: `dpp/{tenant_id}/{yyyy}/{mm}/{dd}/{run_id}/`
- envelope: `pack_envelope.json`

### 13.2 Lifecycle rules (필수)
- Expiration: 30 days
- Abort incomplete multipart uploads: 7 days
- Block public access: ON

### 13.3 Presigned URLs
- GET 시점에 presigned URL 생성
- TTL=600s

---

## 14) 보안/악용 방지 (최소)

- API Key auth + tenant scope
- owner guard 실패는 404 stealth
- polling rate limit(tenant token bucket)
- Rate Limit (DEC-4207): tenant 기준 60 req/min (default). 초과 시 429 + `Retry-After: 30` + `X-RateLimit-Limit/Remaining/Reset` 헤더.
- PII 최소 로깅(입력 raw 금지)

---

## 15) Observability & Ops

### 15.1 Logs (구조화 JSON)
필수 필드:
- service(api/worker/reaper)
- run_id, tenant_id, trace_id
- version_before/version_after
- finalize_stage
- money_state + reserved/charge/refund micros
- error.reason_code (있을 때)

### 15.2 Health endpoints
- /healthz
- /readyz (DB/Redis/S3/SQS)

---

## 16) 테스트/품질 게이트

### 16.1 단위 테스트(필수)
- money micros 변환(Decimal)
- payload_hash canonicalization
- lua scripts (reserve/settle/refund_full)
- optimistic locking:
  - claim 실패 시 side-effect 0 보장
  - final commit 실패 시 side-effect 0 보장

### 16.2 통합(E2E) 테스트(권장)
- docker-compose로 postgres/redis/localstack 띄우고:
  - POST submit
  - worker 실행
  - GET polling 완료 확인
  - 예산 ledger 정합 확인

### 16.3 레이스 테스트(필수)
- worker와 reaper를 같은 run에 대해 동시에 finalize하도록 유도
- 기대:
  - finalize_stage='COMMITTED'는 1회
  - settle는 1회
  - loser는 reserve/settle 호출 0

---

## 17) 로컬 개발(docker-compose)

- postgres:15
- redis:7
- localstack: S3,SQS
- init.sh:
  - s3 bucket create
  - sqs queue create
  - seed tenant/api_key + initial budget

---

## 18) 마일스톤 (Claude Code 실행 순서)

- MS0: Repo bootstrap + docker-compose + alembic
- MS1: Reserve + Idempotency + POST /v1/runs
- MS2: GET /v1/runs/{run_id} + presigned URL
- MS3: Worker happy-path + finalize 2단계
- MS4: Reaper + timeout finalize
- MS5: Race tests + rate limit + hardening

---

## 19) Acceptance Criteria (DoD)
- AC-4210: terminal finalize exactly-once + loser side-effect 0
- AC-4211: money float 사용 0 + ledger 정합
- AC-4202: idempotency 정상(중복 생성/과금 없음)
- AC-4209: retention 규칙 준수(owner 410/non-owner 404)
- AC-4205: zombie run이 reaper로 종료/정산됨

---

## 20) Claude Code 운용 세팅(참고: APPLY_NOTES)

### 20.1 `.claude/settings.json` 권장 핵심
- permissions allowlist: `python`, `pytest`, `ruff`, `mypy`, `alembic`, `docker`, `docker compose`, `git`, `curl`
- hooks: (옵션) 파일 변경 시 `ruff`/`pytest -q` 자동 실행(시간 제한)

### 20.2 Claude Code 작업 규칙(이 프로젝트에서 잠금)
- destructive command(rm -rf, drop db 등) 실행 전 반드시 “dry-run/confirm” 패턴 사용
- PR 단위: MS0~MS5 마일스톤 기준으로 작은 커밋 유지
- 모든 결정 잠금은 “이 문서”와 `DPP_v0_4_2_2_Report...`을 우선한다

---

## 21) Claude Code Kickoff Prompt (복붙용)

```text
PROJECT: DPP (Decision Pack Platform)
TARGET: v0.4.2.2 implementation (API + Worker + Reaper)
STACK: Python/FastAPI + Postgres + Redis + S3 + SQS (LocalStack)
DOC: DPP_v0_4_2_2_Detailed_Dev_Spec_for_Claude_Code_20260213.md is source of truth.

NON-NEGOTIABLES:
- DEC-4210 Optimistic Locking: runs.version DB-CAS. terminal finalize exactly once.
- DEC-4211 Money Type: internal money in USD_MICROS (BIGINT). no float.
- 2-step finalize with finalize_token/stage; loser side-effects must be 0.
- Idempotency: lock-on-key + payload_hash mismatch => 409.
- Owner guard: non-owner 404 stealth; retention expired => owner 410.

EXECUTE MILESTONES:
MS0 bootstrap -> MS1 POST -> MS2 GET -> MS3 Worker -> MS4 Reaper -> MS5 tests/hardening.

DONE DEFINITION:
- ruff + mypy + pytest green
- e2e test passes on docker-compose(localstack)
- race test proves exactly-once finalize+settle
```

---

## 22) MCP Tools (Agent-Ready Distribution Signals)

v0.4.2.2에서 MCP(또는 에이전트)가 호출할 최소 3종 tool 신호를 제공한다.
- `dpp_ocr_run_submit`      -> POST /v1/runs (pack_type="ocr")
- `dpp_url_run_submit`      -> POST /v1/runs (pack_type="url")
- `dpp_decision_run_submit` -> POST /v1/runs (pack_type="decision")

### 22.1 Tool → API 매핑(잠금)
- tool 입력을 RunCreateRequest로 변환:
  - `reservation.max_cost_usd` = tool.max_cost_usd
  - `reservation.timebox_sec` = tool.timebox_sec (없으면 90)
  - `reservation.min_reliability_score` = tool.min_reliability_score (없으면 0.8)
  - `inputs` = tool 전용 payload

### 22.2 Tool input schema (초안; report와 정렬)
- dpp_url_run_submit
```json
{
  "type": "object",
  "required": ["urls", "max_cost_usd"],
  "properties": {
    "urls": { "type": "array", "items": { "type": "string", "format": "uri" }, "maxItems": 30 },
    "max_cost_usd": { "type": "number", "minimum": 0.01 },
    "timebox_sec": { "type": "integer", "minimum": 1, "maximum": 90 },
    "min_reliability_score": { "type": "number", "minimum": 0, "maximum": 1 }
  }
}
```

- dpp_ocr_run_submit
```json
{
  "type": "object",
  "required": ["input_files", "max_cost_usd"],
  "properties": {
    "input_files": { "type": "array", "items": { "type": "string" }, "minItems": 1, "maxItems": 10 },
    "max_cost_usd": { "type": "number", "minimum": 0.01 },
    "ocr_profile": { "type": "string", "enum": ["P1","P2A","P2B","P3"] },
    "language": { "type": "string", "default": "kor+eng" },
    "timebox_sec": { "type": "integer", "minimum": 1, "maximum": 90 },
    "artifacts": {
      "type": "object",
      "properties": {
        "include_markdown": { "type": "boolean" },
        "include_docx": { "type": "boolean" }
      }
    }
  }
}
```

- dpp_decision_run_submit
```json
{
  "type": "object",
  "required": ["question", "max_cost_usd"],
  "properties": {
    "question": { "type": "string" },
    "context": { "type": "string" },
    "max_cost_usd": { "type": "number", "minimum": 0.01 },
    "timebox_sec": { "type": "integer", "minimum": 1, "maximum": 90 },
    "min_reliability_score": { "type": "number", "minimum": 0, "maximum": 1 }
  }
}
```

규칙
- 각 tool은 RunReceipt(202)를 반환한다.
- 완료 결과는 반드시 GET /v1/runs/{run_id}로 폴링한다(동기 반환 금지).


---

## 23) Reconcile Job (DEC-4206 “atomic-ish” 보강)

원칙적으로 2단계 finalize + winner-only side-effect로 **일관성**이 유지되지만,
아래 케이스에서는 “reconcile”이 필요할 수 있다(예: S3 업로드 성공 후 DB commit 직전 크래시).

Reconcile 배치(권장; 1~5분 간격)
- 대상:
  - status='PROCESSING' AND finalize_stage='CLAIMED' AND finalize_claimed_at < now()-5min
  - status='PROCESSING' AND lease_expires_at < now() (reaper와 중복 방지: version CAS 사용)
- 동작(항상 DB-CAS로 claim):
  - winner claim 후 S3 존재 확인(head_object)
  - 존재하면: settle + COMPLETED commit
  - 없으면: settle(min_fee) + FAILED commit

Reconcile은 “최후의 안전장치”이며 정상 경로에서 개입하지 않아야 한다.

---

## 24) Best Practices Digest (4개 참고문서 반영)

(1) Instruction Dilution 방지
- 이 문서 = 구현의 단일 근거. 다른 메모/아이디어는 OPEN/DEC로 격리한다.

(2) Milestone-driven small commits
- MS0~MS5 단위로 커밋/PR을 쪼개고, 매 마일스톤마다 pytest green을 유지한다.

(3) Exactly-once side-effect discipline
- DB-CAS claim 이전에 S3/Redis settle 같은 side-effect를 절대 수행하지 않는다.
- claim 실패(0 rows)면 즉시 stop + ack(작업 중단)한다.

(4) Test pyramid
- unit(돈/해시/lua) → integration(localstack) → race(강제 지연) 순으로 쌓는다.

(5) Dev ergonomics
- LocalStack + init script로 “원클릭 재현”을 보장한다.
- ruff/mypy/pytest를 CI에서 필수 게이트로 둔다.

(6) Security hygiene
- 입력 raw(PII/콘텐츠) 로깅 금지(해시/길이/타입만).
- owner-guard + stealth 404는 모든 GET에 공통 적용한다.

---

## Appendix: External references (official)
- RFC 9457: https://www.rfc-editor.org/rfc/rfc9457
- AWS S3 Presigned URL (User Guide): https://docs.aws.amazon.com/AmazonS3/latest/userguide/ShareObjectPreSignedURL.html
- AWS S3 Lifecycle rules (expiration + abort multipart): https://docs.aws.amazon.com/AmazonS3/latest/userguide/intro-lifecycle-rules.html
- AWS SQS Visibility Timeout: https://docs.aws.amazon.com/AWSSimpleQueueService/latest/SQSDeveloperGuide/sqs-visibility-timeout.html
- Redis EVAL command: https://redis.io/docs/latest/commands/eval/
- Redis EVALSHA command: https://redis.io/docs/latest/commands/evalsha/
- OWASP API Security Top 10: https://owasp.org/www-project-api-security/
