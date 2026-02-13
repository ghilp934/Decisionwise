DPP (Decision Pack Platform) v0.4.2.2 Report
(Hardening Patch Integrated — B2A / Agent-Centric API Platform)

As-of: 2026-02-13 (Asia/Seoul)
Status: READY FOR IMPLEMENTATION (Mandatory Fixes Locked: DEC-4210/4211)
Owner: Sung

======================================================================
[AUTO-INSERT / SESSION BOOT SWITCH v3] (Baseline Charter)
======================================================================
[AUTO-INSERT / SESSION BOOT SWITCH v3]
1) 목표: ‘정답’보다 ‘의사결정·구현 가능한 상태’(정의·근거·다음 행동)를 만든다.
2) Preflight(필수): 입력·형식·인코딩·폰트·긴 라인·페이지/행·이미지 앵커 등 깨짐 포인트를 선탐지, 치명적이면 즉시 인터럽트.
3) Spec Lock: 목적/범위/비범위/성공기준 + 불변조건(값·수치·ID·순서) + 금지사항을 선고정한다.
4) Determinism Lock: 임계치/윈도우/TTL/기본옵션은 “프로파일 vX.Y”로 잠그고, 변경은 DEC 1줄로만 기록한다.
5) ASSUMPTION_POLICY: 추정 금지; 불확실은 ASMP/OPEN으로 격리(표시만), 최종 산출물에 TBD를 무단 방치하지 않는다.
6) 리서치 시 3-게이트(Access→Quality→Relevance) 통과만 사용, 우회 접근/페이월 우회 금지.
7) SOURCE_BUDGET/TIMEBOX/STOP_RULE: 한계를 선고정하고 도달 즉시 최소 결론+OPEN/ASMP로 종료한다.
8) Sandboxing(필수): 원본 보존 + 격리 환경에서 작업(권한/네트워크/시크릿 최소화, 로그 민감정보 금지).
9) Static Checks(필수): ID/참조 무결성·금지 표현·스키마/린트 검증을 반복, 실패 시 원인+수정안을 우선 출력한다.
10) Postflight QA: 누락·중복·단위/날짜·표기 통일·충돌 + 렌더링(PDF 글리프/오버플로우) 스모크 테스트 후 끝낸다.

======================================================================
0. CHANGELOG (v0.4.2 → v0.4.2.2 Mandatory Fixes)
======================================================================
v0.4.2.1은 v0.4.2(B2A Core Specs Integrated)의 “운영상 구멍(행간 리스크)”을 폐쇄하는 Hardening Patch이다.
핵심은 “Async Runs + JSON First + Machine-Readable Errors” 위에, 아래 4개 P0를 ‘선택지 없이’ 결정론으로 잠그는 것이다.

P0-1) 결과 영속성(Persistence) 부재 → 영구 저장(Object Storage) + URL 반환으로 해결
P0-2) 멱등성(Idempotency) 구현 누락 → Idempotency-Key + lock-on-key로 중복 런/중복 과금 방지
P0-3) 좀비 런(Zombie / Stuck Processing) 처리 부재 → lease TTL + Reaper로 강제 종료/정산
P0-4) API Key 권한 범위(AuthZ) 모호성 → owner guard + stealth 404 + run_id 비추측성

추가로, “돈(Money) ↔ 상태(State)” 동기화 실패를 근본 원인으로 보고,
2-Phase State Machine(Execution State × Financial State)을 불변식으로 잠근다(“Golden Rule”).

v0.4.2.2는 v0.4.2.1(Hardening Patch Integrated)에 대한 감사(Mandatory Fixes) 2개를 추가 잠금한 패치다.
- DEC-4210: RunRecord.version 기반 Optimistic Locking(DB-CAS)로 Worker/Reaper 동시 종료 레이스를 차단
- DEC-4211: Money Type을 USD_MICROS(BIGINT)로 박제하고, API/헤더는 4dp decimal string만 허용

======================================================================
1. SPEC LOCK (목표 / 범위 / 비범위 / 성공기준)
======================================================================
1.1 목표(Goals)
- DPP를 Agent-Centric API Platform으로 운영 가능한 수준까지 “결정론 + 무결성”을 잠근다.
- 에이전트가 90초 이상 대기하지 않는 전제에서, Async Polling 기반으로 안정적인 결과 전달을 보장한다.
- 비용/예산/정산이 동시성에서 깨지지 않도록 “Reserve-then-Settle”을 강제하고, 공격(무료 컴퓨팅/폴링 폭탄)을 방어한다.
- 결과가 “사라지지 않는(Persistence)” 상태로 남도록 영구 저장소를 명세에 포함한다.
- 에이전트가 기계적으로 판단 가능한 표준 에러(Problem Details)와 reason_code를 제공한다.

1.2 범위(Scope)
- Runs API (POST /v1/runs, GET /v1/runs/{run_id}) 및 PackEnvelope JSON 스키마(기계 우선)
- AuthN/AuthZ (API Key) + Multi-Tenancy owner guard + Stealth mode
- Budget 모델(Reserve/Settle/Refund) + Redis Lua atomicity + Reaper(좀비 처리)
- 결과 저장(Permanent Storage) + Retention/Lifecycle(비용 폭주 방지)
- MCP Tool 3개 스키마(Agent-friendly distribution signals)
- Gateway 레벨 에러 매핑(HTTP ↔ reason_code ↔ MCP isError 규칙)

1.3 비범위(Non-Goals)
- UI/웹앱 UX 상세 설계(별도)
- “결과의 내용” 품질 향상(프롬프트/모델/평가의 고도화)은 별도 트랙
- 특정 클라우드 벤더 종속 구현(단, S3-Compatible API를 기준 인터페이스로 잠금)
- 결제 수단/세금계산서/정산 회계 시스템 연동(별도)

1.4 성공기준(Success Criteria) — 운영 KPI
- Run Retrieval Durability: COMPLETED 결과 30일 보존(기본) + 만료 전 404/증발 0건
- Exactly-Once Billing: Idempotency-Key 동일 요청에서 중복 과금 0건
- Zombie Rate: PROCESSING이 lease timeout을 넘겨 영구 stuck 0건
- AuthZ Leakage: 403로 존재 유무 누출 금지, Stealth 404 준수 100%
- P95 GET /runs latency: < 500ms, POST /runs: < 500ms

======================================================================
2. KEY CONCEPTS (Runs / Packs / Envelopes)
======================================================================
2.1 Runs (Async Polling)
- Submit(POST /v1/runs): 202 Accepted + run_id 즉시 반환
- Poll(GET /v1/runs/{run_id}): 상태 조회 + 완료 시 결과 포인터(또는 결과 일부) 반환
- Execution status: QUEUED → PROCESSING → COMPLETED | FAILED | EXPIRED

2.2 Pack Types (Core Services)
- OCRPack: 이미지/PDF → 구조 보존 텍스트 + 메타(패스/프리셋/오류)
- URLPack: URL 리스트 → Access/Quality/Relevance 3-Gate 스크리닝 + KEEP/DISCARD 로그
- IRPack: IR/사업계획 입력 → Claim–Evidence 구조화 + 수치/단위 1:1 보존
- CompliancePack: KR AI 표시/투명성, PIPA, 표시광고, 저작권, ToS 준수 고지/레드라인/완화책
- EvalPack: 점수(0–100) + 근거 + OPEN/ASMP 분리

2.3 PackEnvelope (JSON First)
- “JSON is King”: data(기계 1등 시민) + artifacts(사람 2등 시민)
- 결과는 “영구 저장”되고, 응답에는 결과 URL(또는 presigned URL)과 해시(무결성)를 포함한다.

PackEnvelope (v0.4.2.2) 요약:
- meta: run_id, created_at, completed_at, profile_version, cost_usd_actual, cost_usd_reserved, latency_ms, trace_id, retention_until
- status: QUEUED | PROCESSING | COMPLETED | FAILED | EXPIRED
- data: key_findings, evidence_map, discard_log, scores, compliance, open, asmp, (pack_type별 세부)
- artifacts: report_markdown(optional), report_docx_url(optional), extra_files(optional)
- pointers: result_object (s3://bucket/key), result_presigned_url(optional), result_sha256

======================================================================
3. ARCHITECTURE (B2A Hardening)
======================================================================
3.1 Components (Authoritative vs Ephemeral 분리)
- API Gateway (HTTP): AuthN/AuthZ, rate limit, cost headers, Problem Details 에러 표준화
- Run Service (Authoritative): RunRecord(DB) + 상태 전이(CAS) + 결과 포인터 저장
- Queue: 작업 큐(단일 구현으로 잠금; DEC-4212)
- Worker Pool: run 실행, evidence gating, pack 생성
- BudgetManager (Redis): Reserve/Settle/Refund를 Redis Lua로 원자 처리(atomic)
- IdempotencyStore (Redis): Idempotency-Key → run_id 매핑 + lock-on-key 동시성 제어
- Lease Manager (Redis): PROCESSING lease TTL(좀비 방지)
- Reaper: lease 만료 런 스윕 → 강제 FAIL(TIMEOUT) + 정산(Settle)
- Object Storage (S3-Compatible): PackEnvelope 결과 JSON + artifact 파일 영구 저장 + Lifecycle(예: 30일 만료)
- Observability: trace_id 전파, structured logs(JSON), metrics, audit logs(PII 최소)

3.2 Authoritative Storage 결론
- Redis는 Ephemeral(락/예약/리스/캐시)만 담당한다.
- Run 상태/메타의 최종 진실(source of truth)은 DB에 둔다.
- COMPLETED 결과는 Object Storage에 저장하고, RunRecord는 결과 포인터(s3_key)와 해시를 가진다.

3.3 DPP Transaction Lifecycle (Deep 6 / 2-Phase State Machine)
불변식(“Golden Rule”):
- 모든 Run은 Reservation(예산 예약) 없이는 시작될 수 없고,
- Settlement(정산) 없이는 종료될 수 없다.

[Phase 1: Submission / API]
  POST /v1/runs (Idempotency-Key)
    -> (Money) Reserve(max_cost_usd)  [atomic]
    -> (State) Create RunRecord(status=QUEUED)
    -> Enqueue(run_id)
    -> 202 Accepted (run_id)

[Phase 2: Execution / Worker]
  Dequeue(run_id)
    -> Acquire PROCESSING lease (TTL)
    -> (State) status=PROCESSING (CAS, lease_token 기록)
    -> Execute pack pipeline (preflight/gates/sandbox/postflight)
    -> Produce PackEnvelope JSON + artifacts

[Phase 3: Termination / Worker or Reaper]
  SUCCESS or FAIL or TIMEOUT
    -> Store result to S3 (PackEnvelope + artifacts)
    -> (Money) Settle(actual_cost) + Refund(reserved-actual or policy) [atomic]
    -> (State) status=COMPLETED|FAILED (CAS)
    -> Persist result pointers + sha256 in RunRecord
    -> Release lease

Reaper(좀비):
  Scan PROCESSING with lease expired
    -> Mark FAILED(timeout)
    -> Settle(minimum_fee_policy) + Refund(rest) [atomic]

======================================================================
4. RUNS API (REST) — B2A Core + Hardening
======================================================================
4.1 AuthN
- Header: Authorization: Bearer dpp_sk_...
- API key는 tenant(user/org) 스코프를 가진다.

4.2 POST /v1/runs (Submit)
Request Headers
- Authorization: Bearer dpp_sk_...
- Content-Type: application/json
- Idempotency-Key: <client-generated key>

Request Body (common)
- pack_type: "ocr" | "url" | "decision" | "compliance" | "eval"
- profile_version: "v0.4.2.2" (default)
- timebox_sec: integer (default 90; hard cap)
- max_cost_usd: number (required; Reserve 상한)
- min_reliability_score: number (0.0~1.0, default 0.8)
- inputs: object (pack_type별)
- artifacts: object (optional) { "include_markdown": bool, "include_docx": bool }
- client: object (optional) { "trace_id": "uuid", "client_name": "...", "client_version": "..." }

Response (202 Accepted): RunReceipt JSON
{
  "run_id": "b1c4a7a5-1f8a-4b2f-9f5b-8a1e8e6a2a10",
  "status": "QUEUED",
  "poll": {
    "href": "/v1/runs/b1c4a7a5-1f8a-4b2f-9f5b-8a1e8e6a2a10",
    "recommended_interval_ms": 1500,
    "max_wait_sec": 90
  },
  "reservation": {
    "max_cost_usd": "0.5000",
    "currency": "USD"
  },
  "meta": {
    "created_at": "2026-02-13T09:00:00Z",
    "trace_id": "..."
  }
}

4.3 GET /v1/runs/{run_id} (Poll)
- owner mismatch / no access: 404 Not Found (Stealth)
- status=QUEUED|PROCESSING: 200 + 상태/힌트
- status=COMPLETED: 200 + result_url + sha256 (+ optionally small inline)
- status=FAILED: 200 + error(reason_code + Problem Details)
- status=EXPIRED: owner=410 Gone (기본), non-owner=404

======================================================================
5. STANDARD ERRORS (Problem Details) + reason_code
======================================================================
- HTTP 에러는 Problem Details 형식(RFC 9457)을 사용한다.
  - https://www.rfc-editor.org/rfc/rfc9457

Problem Details 예시
{
  "type": "https://dpp.api/errors/budget-exceeded",
  "title": "Budget Exceeded",
  "status": 402,
  "detail": "Insufficient reserved budget for max_cost_usd.",
  "instance": "/v1/runs/b1c4a7a5-1f8a-4b2f-9f5b-8a1e8e6a2a10",
  "extensions": {
    "reason_code": "BUDGET_DRAINED",
    "balance_remaining": 0.01,
    "reservation_required": 0.50
  }
}

======================================================================
6. MCP TOOLS (3) — Agent-Ready Distribution Signals
======================================================================
- dpp_ocr_run_submit     -> POST /v1/runs (pack_type="ocr")
- dpp_url_run_submit     -> POST /v1/runs (pack_type="url")
- dpp_decision_run_submit-> POST /v1/runs (pack_type="decision")
(각 tool은 RunReceipt를 반환하고, 완료 결과는 GET /v1/runs로 폴링한다.)

======================================================================
7. DEC CARDS — v0.4.2.2 Determinism Lock
======================================================================
DEC-4201 Persistence: S3-Compatible Object Storage + 30일 Lifecycle + DB pointer
DEC-4202 Idempotency: Idempotency-Key + SETNX lock-on-key + payload_hash mismatch=409
DEC-4203 Reserve-then-Settle: Submit reserve, Complete settle, Fail/Timeout minimum_fee
DEC-4204 AuthZ: owner guard + stealth 404 + run_id UUID v4
DEC-4205 Zombie: lease TTL + Reaper 강제 종료/정산
DEC-4206 Termination Atomic Commit: S3 write + settle + status transition = atomic-ish (reconcile 포함)
DEC-4207 Polling Abuse: GET rate limit/quota, 429 Retry-After
DEC-4208 Cost Headers: X-DPP-* 표준화
DEC-4209 Retention: 30일 이후 owner=410, non-owner=404

DEC-4210 Optimistic Locking: RunRecord.version 기반 DB-CAS(0 rows=이미 처리됨)
DEC-4211 Money Type: 모든 금전은 USD_MICROS(BIGINT)로 저장/계산, API는 4dp decimal string
DEC-4212 Queue = SQS-Compatible (Production) + LocalStack(Dev)

(각 DEC 상세는 “Hardening Patch 상세 섹션”에서 구현 규칙과 함께 재정의된다.)

======================================================================
8. DATA MODEL (Authoritative DB + Redis Keys)
======================================================================
DB: RunRecord(요약)
- run_id(UUID), tenant_id, pack_type, status
- idempotency_key, payload_hash
- version (optimistic lock)
- reservation_max_cost_usd_micros, actual_cost_usd_micros, minimum_fee_usd_micros
- result_bucket, result_key, result_sha256, retention_until
- lease_token, lease_expires_at
- last_error_reason_code, trace_id
Redis(요약)
- budget:{tenant_id}:balance_usd_micros
- reserve:{run_id}
- idem:{tenant_id}:{idempotency_key}
- idem_lock:{tenant_id}:{idempotency_key}
- lease:{run_id}

======================================================================
9. REDIS LUA SCRIPTS (Atomic Money-State Control)
======================================================================
Redis Lua(EVAL)는 원자 실행이 가능하다는 전제를 사용한다(단일 스레드 이벤트 루프).
- Reserve: balance에서 max_cost 차감 + reserve 기록
- Settle: reserved와 actual/fee로 refund 계산 + balance 환급 + reserve 삭제
- Reaper refund: TTL 만료 예약금 복원

======================================================================
10. SECURITY (B2A Reality)
======================================================================
- 객체 수준 권한(BOLA) 방지: owner guard 필수
  - OWASP API Top 10(2023) 참고(최상위 위험): https://www.akamai.com/site/en/documents/brief/2023/owasp-api-top-10.pdf
- Reserve 모델로 무료 컴퓨팅/비용 고갈 공격을 방어
- 결과 링크는 presigned URL(짧은 TTL) 중심, bucket public access off
- S3 durability/보존 참고:
  - https://aws.amazon.com/s3/
  - https://docs.aws.amazon.com/AmazonS3/latest/userguide/DataDurability.html

======================================================================
APPENDIX A. Reference Links (Standards & Primary Docs)
======================================================================
- RFC 9457 Problem Details: https://www.rfc-editor.org/rfc/rfc9457
- MCP spec: https://modelcontextprotocol.io/specification/
- Stripe idempotency: https://stripe.com/docs/idempotency


======================================================================
13. HARDENING PATCH — DETAILED SPEC (Implementation-Grade)
======================================================================

13.1 결정론적 상태 머신: Execution State × Financial State
------------------------------------------------------------
A) Execution State (status)
- QUEUED
- PROCESSING
- COMPLETED
- FAILED
- EXPIRED

B) Financial State (money_state)
- NONE            (생성 전; 외부 노출 없음)
- RESERVED        (max_cost_usd_micros 홀드 완료)
- SETTLED         (actual_cost 확정 + refund 처리 완료)
- REFUNDED        (예약금 전액 환불; 실행 시작 못함/취소/만료)
- DISPUTED        (예외: reconcile 필요)

Golden Rule (불변식)
- status가 QUEUED/PROCESSING/COMPLETED/FAILED 중 어느 것이든,
  money_state는 최소 RESERVED 이상이어야 한다.
- terminal(COMPLETED/FAILED/EXPIRED) 상태로 가기 전에는 SETTLED 또는 REFUNDED가 반드시 성립해야 한다.
- status=PROCESSING은 유효한 lease_token 없이는 존재할 수 없다.

허용 전이(요약)
- NONE -> RESERVED (POST 성공)
- RESERVED + QUEUED -> PROCESSING (worker start + lease)
- PROCESSING -> COMPLETED + SETTLED
- PROCESSING -> FAILED + SETTLED (실패)
- PROCESSING -> FAILED(timeout) + SETTLED (reaper)
- QUEUED -> FAILED + REFUNDED (큐잉 실패/취소 정책 시)
- COMPLETED/FAILED -> EXPIRED (retention 만료; 결과 삭제 후)


13.1.1 동시성 가드(Optimistic Locking) — DEC-4210 Implementation
---------------------------------------------------------------
목적: Worker vs Reaper(좀비) “죽음의 경주”에서, DB가 최종 진실로서 오직 1회만 terminal 전이를 허용한다.

DB 스키마(필수)
- runs.version BIGINT NOT NULL DEFAULT 0
- 모든 상태 전이(특히 terminal)는 반드시 version 조건을 포함하는 UPDATE로만 수행한다.
- UPDATE가 0 rows affected이면 “이미 처리됨”으로 간주하고, 추가 부작용(정산/환불/결과 노출/삭제)을 절대 수행하지 않는다.

규칙(잠금)
A) Terminal 전이(Worker/ Reaper 공통)
- Worker(성공/실패)와 Reaper(timeout)는 terminal 전이를 시도할 때 아래 패턴을 사용한다.
  UPDATE runs
    SET status=?, money_state=?, ..., version=version+1
    WHERE run_id=? AND version=? AND status='PROCESSING';

- Reaper는 추가로 lease_expires_at < now() 조건을 포함해야 한다.
- Worker는 lease_token 일치 조건을 포함해야 한다(가능하면).

B) PROCESSING 전이(Worker start)
- 동시에 여러 worker가 run_id를 잡는 상황을 막기 위해, PROCESSING 전이도 version 조건을 포함한다.
  UPDATE runs
    SET status='PROCESSING', lease_token=?, lease_expires_at=?, version=version+1
    WHERE run_id=? AND version=? AND status='QUEUED';

C) Side-effect 순서(원칙)
- Cross-system(Redis/S3/DB) 완전 원자성은 불가하므로,
  “DB terminal CAS 승리”를 확인한 주체만 Redis settle/refund 및 결과 노출을 진행한다.
- CAS 승리 전에는 settle/refund를 절대 수행하지 않는다(승리 후 수행).

Acceptance Criteria (AC-4210)
- AC-4210-1: 동일 run_id에 대해 terminal status(COMPLETED/FAILED/EXPIRED)는 정확히 1회만 커밋된다.
- AC-4210-2: Worker와 Reaper가 동시에 terminal 전이를 시도해도, 한 쪽은 반드시 0 rows affected로 종료한다.
- AC-4210-3: 0 rows affected인 쪽은 Redis settle/refund, 결과 포인터 업데이트, S3 삭제/노출 등 어떤 side-effect도 수행하지 않는다.
- AC-4210-4: Concurrency Torture 테스트에서 “유령 정산(이중 settle/refund)”이 재현되지 않는다(24.2 통과).
- AC-4210-5: 모든 status 전이 로그에 (run_id, prev_version, next_version, actor=worker|reaper) 필드가 남는다.

참고(근거)
- Optimistic locking은 version 컬럼 + UPDATE ... WHERE version=... 패턴으로 구현하며, 0 rows affected를 충돌로 처리한다. 

13.1.2 금전 데이터 표현(Money Type) — DEC-4211 Implementation
---------------------------------------------------------------
목적: Float/DOUBLE로 인한 누적 오차를 원천 차단하고, 예산·정산·환불의 완전한 일치(ledger consistency)를 보장한다.

단위(잠금)
- 내부 표준 단위: USD_MICROS (1 USD = 1,000,000 micros)
- 저장/계산/정산/환불은 오직 정수(micros)로만 수행한다.
- 외부 노출(REST/MCP headers/body)은 “decimal string(고정 4dp)”로만 표현한다.

DB 타입(잠금; 권장 1안)
- reservation_max_cost_usd_micros BIGINT NOT NULL
- actual_cost_usd_micros BIGINT NULL
- minimum_fee_usd_micros BIGINT NOT NULL DEFAULT 0
- budget/balance 또한 BIGINT micros로 통일한다.

Redis 타입(잠금)
- budget:{tenant_id}:balance_usd_micros = BIGINT
- reserve:{run_id}:reserved_usd_micros = BIGINT (TTL 동일)

API 입력(잠금)
- max_cost_usd는 "decimal string"으로 받는다. (예: "0.5000")
- scale(소수 자릿수) 최대 4자리. 초과 시 422 INVALID_MONEY_SCALE
- 지수 표기(1e-3), NaN, Infinity 등은 금지.

API 출력/헤더(잠금)
- 모든 금전 출력은 4dp 고정 문자열로 렌더링한다.
- 내부 micros -> 4dp 렌더링은 “HALF_UP” 반올림 규칙으로 결정론적 변환한다.
- X-DPP-* 비용/예산 헤더는 4dp 고정 문자열만 허용한다(DEC-4208).

Acceptance Criteria (AC-4211)
- AC-4211-1: 코드베이스에서 float/double/real을 금전 저장/계산에 사용하지 않는다(정적 검사 포함).
- AC-4211-2: DB/Redis의 모든 금전 값은 BIGINT micros로 저장된다(스키마/마이그레이션 포함).
- AC-4211-3: API는 max_cost_usd를 문자열로만 허용하며, 4dp 초과/지수 표기 입력은 422로 거부한다.
- AC-4211-4: 어떤 경우에도 actual_cost_usd_micros > reservation_max_cost_usd_micros 가 DB에 커밋되지 않는다(초과 시 DISPUTED 또는 cap 정책).
- AC-4211-5: X-DPP-Cost-Used / Reserved / Budget-Remaining 헤더는 4dp 문자열이며, 내부 micros ledger와 값이 일치한다(표시 반올림은 display-only).

참고(근거)
- PostgreSQL money 타입 문서: floating point를 money에 쓰지 말 것을 명시
  https://www.postgresql.org/docs/current/datatype-money.html
- PostgreSQL numeric 타입 문서: exactness가 필요한(금전 포함) 경우 numeric 권장
  https://www.postgresql.org/docs/current/datatype-numeric.html
- MySQL DECIMAL 문서: monetary data 등 exact precision 필요 시 DECIMAL/NUMERIC 권장
  https://dev.mysql.com/doc/refman/8.4/en/fixed-point-types.html
13.2 결과 영속성(Persistence) — DEC-4201 Implementation
---------------------------------------------------------
Object Storage: S3-Compatible API (AWS S3 또는 동등)
- Result Object (필수): pack_envelope.json (application/json)
- Artifact Objects (옵션): report.md, report.docx, 기타 파일

Key Naming (deterministic)
- Bucket: dpp-results
- Key root: dpp/{tenant_id}/{yyyy}/{mm}/{dd}/{run_id}/
- Envelope key: .../pack_envelope.json
- Artifacts key: .../artifacts/{name}

Retention/Lifecycle (필수)
- Expiration: 30 days after object creation
- Abort incomplete multipart uploads: 7 days
  참고: https://docs.aws.amazon.com/AmazonS3/latest/userguide/mpu-abort-incomplete-mpu-lifecycle-config.html
- Optional(추후): Glacier tiering는 v0.4.2.2 범위 밖

Retrieval Model (3시간 뒤 폴링 대응)
- DB에는 result_bucket/result_key가 영구 저장된다.
- GET /v1/runs/{run_id}는 요청 시점에 presigned URL을 새로 생성하여 반환한다.
  (presigned URL TTL 기본 10분, profile로 조정)

Integrity
- pack_envelope.json 저장 후 sha256을 계산하여 RunRecord.result_sha256에 기록한다.
- GET 응답에 sha256을 포함해 클라이언트가 다운로드 무결성 검증 가능하도록 한다.

13.3 Idempotency — DEC-4202 Implementation (Lock-on-Key)
---------------------------------------------------------
요구사항
- Idempotency-Key는 “POST /v1/runs”에서만 의미를 가진다.
- Key는 tenant 범위로 격리된다: (tenant_id, idempotency_key)가 유일.
- Key 충돌/재사용은 허용하되, payload_hash가 다르면 409로 차단한다.

Payload Hash (deterministic)
- canonical JSON serialization(키 정렬, 공백 제거) 후 SHA-256
- 제외 필드: client.trace_id, client.client_version 등 “동일 요청의 의미를 바꾸지 않는 필드”는 해시 대상에서 제외
- pack_type, inputs, timebox_sec, max_cost_usd, min_reliability_score, artifacts는 포함(중요)

Algorithm (atomic-ish)
1) compute payload_hash
2) acquire idem_lock:{tenant}:{key} via SETNX with TTL=5s
   - 실패(락 존재) 시: idem mapping 조회 후 존재하면 202(기존 run) 반환
3) idem mapping 조회:
   - 없음: reserve_budget -> create RunRecord -> set idem mapping -> enqueue -> 202
   - 있음:
      - hash 동일: 202 + 기존 run receipt
      - hash 다름: 409 IDEMPOTENCY_CONFLICT
4) release lock (or let TTL expire)

TTL 정책
- idem mapping TTL: min(retention_days, 30일)로 기본 30일
  (목표: run 결과가 살아있는 동안 같은 키로 재요청해도 과금/중복 생성이 없게)

13.4 Reserve-then-Settle — DEC-4203 Implementation (Anti-Abuse)
---------------------------------------------------------------
Definitions
- reserved_usd = max_cost_usd (submit 시 홀드)
- actual_cost_usd = 실행 후 계산(LLM/API/Fetcher/스토리지 비용 합산)
- minimum_fee_usd = max(0.005, 0.02 * reserved_usd)  (v0.4.2.2 잠금)
  - cap: minimum_fee_usd <= 0.10 (과도한 수수료 방지)

Rules
- Submit:
  - if balance < reserved_usd: 402 BUDGET_DRAINED
  - else: reserve (balance -= reserved_usd), money_state=RESERVED
- Completion success:
  - charge = actual_cost_usd (단, charge <= reserved_usd 를 워커가 보장)
  - refund = reserved_usd - charge
  - settle(refund), money_state=SETTLED
- Fail/Timeout:
  - charge = minimum_fee_usd
  - refund = reserved_usd - charge
  - settle(refund), money_state=SETTLED
- Reservation Expiry (예외):
  - reserved가 있고 run이 시작되지 않았거나(QUEUE stuck), 시스템 장애로 terminal로 가지 못하는 경우
  - reservation TTL(기본 1시간)이 만료되면 Reaper/Job이 REFUNDED 처리
  - 단, REFUNDED는 RunRecord에 기록되어 중복 실행/중복 과금 방지

13.5 Zombie / Stuck — DEC-4205 Implementation (Lease + Reaper)
---------------------------------------------------------------
Lease
- acquire: SETNX lease:{run_id} = lease_token TTL=120s
- heartbeat: worker가 30s마다 lease TTL 갱신(extend)
- release: terminal 전이 시 lease 삭제

Reaper
- interval: 30s
- scan: DB에서 status=PROCESSING and lease_expires_at < now
- action:
  1) status=FAILED (reason_code=WORKER_TIMEOUT) CAS로 전이(lease_token 확인)
  2) Settle(minimum_fee) + Refund 수행
  3) failure envelope optional 저장(디버그용; PII 최소)
  4) lease 정리

Client Experience
- GET은 max_wait_sec(90) 및 recommended_interval_ms를 제공하여 무한 대기/폭탄 방지

13.6 AuthZ Stealth — DEC-4204 Implementation (Owner Guard)
-----------------------------------------------------------
- RunRecord에는 tenant_id(owner)가 반드시 저장된다.
- GET /v1/runs/{run_id}:
  - DB에서 run_id 조회 후 owner_id 비교
  - 불일치/없음: 404 Not Found (RUN_NOT_FOUND_STEALTH)
- 403을 반환하지 않는다(존재 유무 누출 방지).
- run_id 생성은 UUID v4(또는 UUIDv7)로, 추측 공격을 낮춘다.

13.7 Gateway Error Mapping & MCP isError Rules (Deterministic)
--------------------------------------------------------------
A) REST API (HTTP)
- POST /v1/runs
  - 202: success (RunReceipt)
  - 400: INVALID_PARAMS / SCHEMA_VALIDATION_FAILED (Problem Details)
  - 401: AUTH_INVALID
  - 402: BUDGET_DRAINED / RESERVATION_FAILED
  - 409: IDEMPOTENCY_CONFLICT
  - 429: RATE_LIMITED
  - 5xx: INTERNAL_ERROR / STORAGE_WRITE_FAILED / UPSTREAM_TIMEOUT

- GET /v1/runs/{run_id}
  - 200: always for valid request + authorized owner (status field drives decisions)
  - 404: RUN_NOT_FOUND_STEALTH (owner mismatch 포함)
  - 401/429/5xx: request-level failures only (Problem Details)

B) MCP Gateway (tool call wrapper)
- tool call success 조건:
  - upstream HTTP 202를 받으면 MCP result.isError=false
- tool call failure 조건:
  - upstream HTTP 4xx/5xx면 MCP result.isError=true
  - content[0].text에는 Problem Details(JSON)를 “그대로” 포함
  - 반드시 extensions.reason_code 포함
- GET 폴링은 MCP tool로 제공하지 않는다(v0.4.2.2 기본). 에이전트는 REST GET을 직접 호출하거나 SDK helper를 사용.

13.8 OpenAPI 자동 생성(Operational Excellence)
------------------------------------------------
- 코드 변경 시 openapi.json을 자동 생성/검증한다.
- 스키마 변경은 CI에서 “breaking change” 감지 시 실패로 처리한다.

======================================================================
14. JSON SCHEMAS (Condensed, Implementation-Facing)
======================================================================
주의: 본 문서의 스키마는 “개념 잠금”이다. 실제 openapi.json이 source of truth다.

14.1 RunCreateRequest (POST body)
{
  "type": "object",
  "required": ["pack_type", "max_cost_usd", "inputs"],
  "properties": {
    "pack_type": { "type": "string", "enum": ["ocr", "url", "decision", "compliance", "eval"] },
    "profile_version": { "type": "string", "default": "v0.4.2.2" },
    "timebox_sec": { "type": "integer", "default": 90, "minimum": 1, "maximum": 90 },
    "max_cost_usd": { "type": "string", "pattern": "^[0-9]+(\\.[0-9]{1,4})?$" },
    "min_reliability_score": { "type": "number", "minimum": 0.0, "maximum": 1.0, "default": 0.8 },
    "inputs": { "type": "object" },
    "artifacts": {
      "type": "object",
      "properties": {
        "include_markdown": { "type": "boolean", "default": false },
        "include_docx": { "type": "boolean", "default": false }
      }
    },
    "client": {
      "type": "object",
      "properties": {
        "trace_id": { "type": "string" },
        "client_name": { "type": "string" },
        "client_version": { "type": "string" }
      }
    }
  }
}

14.2 RunReceipt (202 body)
{
  "type": "object",
  "required": ["run_id", "status", "poll", "reservation", "meta"],
  "properties": {
    "run_id": { "type": "string" },
    "status": { "type": "string", "enum": ["QUEUED"] },
    "poll": {
      "type": "object",
      "required": ["href", "recommended_interval_ms", "max_wait_sec"],
      "properties": {
        "href": { "type": "string" },
        "recommended_interval_ms": { "type": "integer" },
        "max_wait_sec": { "type": "integer" }
      }
    },
    "reservation": {
      "type": "object",
      "required": ["max_cost_usd", "currency"],
      "properties": {
        "max_cost_usd": { "type": "string" },
        "currency": { "type": "string", "enum": ["USD"] }
      }
    },
    "meta": {
      "type": "object",
      "required": ["created_at"],
      "properties": {
        "created_at": { "type": "string" },
        "trace_id": { "type": "string" }
      }
    }
  }
}

14.3 RunStatusResponse (GET body)
- status=QUEUED|PROCESSING
{
  "type": "object",
  "required": ["run_id", "status", "meta"],
  "properties": {
    "run_id": { "type": "string" },
    "status": { "type": "string", "enum": ["QUEUED", "PROCESSING", "COMPLETED", "FAILED", "EXPIRED"] },
    "progress": { "type": "number", "minimum": 0, "maximum": 1 },
    "meta": { "type": "object" },
    "result": { "type": "object" },
    "error": { "type": "object" }
  }
}

======================================================================
15. MCP TOOL SCHEMAS (Full Draft)
======================================================================
15.1 Common Output: RunReceipt (same as REST 202)

15.2 dpp_ocr_run_submit inputSchema (draft)
{
  "type": "object",
  "required": ["max_cost_usd", "inputs"],
  "properties": {
    "max_cost_usd": { "type": "string", "pattern": "^[0-9]+(\\.[0-9]{1,4})?$" },
    "timebox_sec": { "type": "integer", "default": 90, "minimum": 1, "maximum": 90 },
    "min_reliability_score": { "type": "number", "default": 0.8, "minimum": 0.0, "maximum": 1.0 },
    "inputs": {
      "type": "object",
      "properties": {
        "images": {
          "type": "array",
          "items": {
            "type": "object",
            "properties": {
              "url": { "type": "string" },
              "base64": { "type": "string" }
            }
          }
        },
        "pdf_url": { "type": "string" }
      }
    },
    "ocr_profile": { "type": "string", "enum": ["P1", "P2A", "P2B", "P3"], "default": "P1" },
    "language": { "type": "string", "default": "kor+eng" },
    "artifacts": {
      "type": "object",
      "properties": {
        "include_markdown": { "type": "boolean", "default": false },
        "include_docx": { "type": "boolean", "default": false }
      }
    }
  }
}

15.3 dpp_url_run_submit inputSchema (draft)
{
  "type": "object",
  "required": ["max_cost_usd", "inputs"],
  "properties": {
    "max_cost_usd": { "type": "string", "pattern": "^[0-9]+(\\.[0-9]{1,4})?$" },
    "timebox_sec": { "type": "integer", "default": 90, "minimum": 1, "maximum": 90 },
    "min_reliability_score": { "type": "number", "default": 0.8, "minimum": 0.0, "maximum": 1.0 },
    "inputs": {
      "type": "object",
      "required": ["urls"],
      "properties": {
        "urls": { "type": "array", "items": { "type": "string" }, "maxItems": 30 }
      }
    },
    "gates": {
      "type": "object",
      "properties": {
        "access": { "type": "boolean", "default": true },
        "quality": { "type": "boolean", "default": true },
        "relevance": { "type": "boolean", "default": true }
      }
    }
  }
}

15.4 dpp_decision_run_submit inputSchema (draft)
{
  "type": "object",
  "required": ["max_cost_usd", "inputs"],
  "properties": {
    "max_cost_usd": { "type": "string", "pattern": "^[0-9]+(\\.[0-9]{1,4})?$" },
    "timebox_sec": { "type": "integer", "default": 90, "minimum": 1, "maximum": 90 },
    "min_reliability_score": { "type": "number", "default": 0.8, "minimum": 0.0, "maximum": 1.0 },
    "inputs": {
      "type": "object",
      "required": ["decision_question", "options"],
      "properties": {
        "decision_question": { "type": "string" },
        "options": { "type": "array", "items": { "type": "string" }, "minItems": 2 },
        "criteria": { "type": "array", "items": { "type": "string" } },
        "context": { "type": "object" }
      }
    }
  }
}

======================================================================
16. NEXT MOVE (기탄 없는 제안)
======================================================================
v0.4.2.2 리빌드 이후 “다음 고비”는 구현 난이도가 아니라 ‘검증/회귀’다.
추천 Next Move는 다음 3개를 “순서대로” 진행하는 것이다.

NM-1) Golden Invariant Test Suite(불변식 테스트) 먼저 작성
- (money_state, status) 조합의 불가능 상태를 테스트로 박아두면, 구현이 흔들리지 않는다.
- 예: status=PROCESSING인데 reserve가 없는 경우는 무조건 실패.

NM-2) Concurrency Torture Test(멱등성/정산 레이스) 시뮬레이터
- 동일 Idempotency-Key 100 동시 요청
- worker crash mid-processing
- reaper가 먼저 timeout 처리하는 경우
=> “돈이 깨지는지”만 보고 PASS/FAIL

NM-3) Reconciliation Job + Audit Log 최소 버전 구현
- 장애는 반드시 난다. “정산/상태/저장소” 불일치를 자동으로 감지/복구하는 루프가 있으면,
  운영에서 치명적인 사고(사기/환불 폭탄)를 막는다.

(이 3개가 끝나면, v0.4.2.2 또는 v0.4.3에서 “확장 pack_type + SDK + 문서 자동화”로 넘어가면 된다.)


======================================================================
17. CORE PACK PIPELINES (v0.4.2.x Baseline, Re-stated)
======================================================================

17.1 OCRPack Pipeline (누락 방지 우선)
------------------------------------------------------------
입력
- images[]: 업로드/URL(정책 허용 범위)
- pdf_url: 렌더링 가능한 PDF(페이지 스크린샷 기반)

처리(요약)
- Preflight: 레이아웃 스니핑(스크린샷/스캔/촬영본) + PSM 잠금
- Pass 1: 큰 제목/브랜드/슬로건
- Pass 2: 본문 블록(문단/컬럼)
- Pass 3: 미세문구(각주/URL/©/워터마크)
- 불확실 표기: (?), [□], A/B 병기 규칙
- 시간 상한: timebox_sec 내; 패스/크롭 상한으로 재귀 금지

출력
- data.text_blocks[]: 페이지/이미지 단위 텍스트(줄바꿈 최대 보존)
- data.meta: ocr_profile, passes, warnings, low_confidence_count
- artifacts(optional): report_markdown, report_docx

핵심 통제
- “존재는 기록”: 읽기 불가 텍스트도 [□]로 누락 방지
- 원본 불변: 입력 파일/URL을 변경/덮어쓰기 금지
- 약관/정책류는 가능하면 OCR 대신 원문 텍스트(HTML/PDF)로 대체(SOURCE=HTML 표식)

17.2 URLPack Pipeline (Access → Quality → Relevance 3-GATE)
------------------------------------------------------------
입력
- urls[] (max 30)
- DQ(decision_question) optional: relevance 판정 강화

Gate A: Access Gate (0단계 게이트)
- HTTPS 필수
- 브라우저 경고/인증서 오류/이상 리다이렉트 없음
- 본문 확인 가능(403/타임아웃/렌더 실패/페이월로 본문 확인 불가 = DISCARD)
- 자동 우회 금지(로그인/결제/클라우드플레어 우회 등 금지)

Gate B: Quality Gate
- 1차 소스 우선: 정부/공공/기관/공식 문서/연구
- 2차 소스: 대형 언론/리서치 요약
- 커뮤니티/홍보자료/기업블로그/협회자료는 기본 DISCARD(요청 시 예외)
- 최신성: 2023+ 엄격 적용(정책/법/가격/스펙은 최신 우선)

Gate C: Relevance Gate
- DQ와 키워드 매칭(주제 적합도)
- 동일 이벤트/동일 기사 중복은 URL 정규화로 제거(utm 제거 등)

출력
- data.keep[]: { url, title, gist, evidence_quote<=25 words, extracted_at, source_tier }
- data.discard[]: { url, reason_code, reason_detail, replacement_hint(optional) }
- data.blocked_logs[]: 정책 차단 로그(SSRF 등)
- artifacts(optional): 통과 URL 텍스트 파일 등

17.3 Decision Pack Pipeline (IR + Compliance + Eval 묶음)
------------------------------------------------------------
입력
- decision_question
- options[2+]
- criteria(optional)
- context(optional): constraints, budget, timeline, market notes, assumptions

출력(요약)
- data.claims[]: claim + supporting_evidence pointers(가능하면 URLPack에서)
- data.scores: EvalPack 점수(0–100) + 부분점수 + 근거
- data.compliance: KR 고지/표시/면책 + 레드라인 + 완화책
- data.open[]: 미결정 이슈(OPEN)
- data.asmp[]: 가정 장부(ASMP) — base + stress(낙관/비관)
- artifacts: report_markdown/docx (옵션)

통제
- 수치/단위: 1:1 보존(재계산/추정 금지)
- 근거 vs 해석 분리
- 출처 접근 불가/페이월/권한 자료는 우회 금지, DISCARD 후 대체 라우팅

======================================================================
18. SMART FETCHER (SSRF/Redirect Defense) — v0.4.1 Strong Boundary 계승
======================================================================
정책
- 자동 리다이렉트 비활성화: FETCH_ALLOW_REDIRECTS=false
- 3xx 발생 시 “홉 단위” 검증 후 수동 follow
- 홉 상한: FETCH_REDIRECT_MAX_HOPS=5

홉 검증(요약)
- scheme: http/https만 허용(파일/ftp 등 금지)
- host: allowlist 또는 정책 기반 허용(프로필)
- DNS resolve: 매 홉마다 재해석(re-resolve)하여 TOCTOU/DNS rebinding 완화
- IP: RFC1918/loopback/link-local 등 사설/특수 대역 차단
- allow_redirects=false로 요청

차단 시
- reason_code 예: SSRF_PRIVATE_IP_BLOCKED, REDIRECT_MAX_HOPS_EXCEEDED, DOMAIN_NOT_ALLOWED
- blocked_logs에 반드시 기록(아래 스키마)

======================================================================
19. BLOCKED_LOGS & DISCARD_LOG (Auditability)
======================================================================
19.1 blocked_logs 스키마(필수)
{
  "ts": "2026-02-13T03:00:00+09:00",
  "component": "SmartFetcher",
  "action": "FETCH_REDIRECT_FOLLOW",
  "target": "http://example.com/redirect",
  "reason_code": "SSRF_PRIVATE_IP_BLOCKED",
  "reason_detail": "Resolved IP 127.0.0.1 is not allowed",
  "severity": "HIGH"
}

19.2 discard_log 스키마(필수; URLPack)
{
  "url": "https://example.com/article",
  "gate": "ACCESS|QUALITY|RELEVANCE",
  "reason_code": "ACCESS_TIMEOUT|PAYWALL|LOW_QUALITY_SOURCE|IRRELEVANT",
  "reason_detail": "timed out after 10s",
  "replacement_hint": "Search official gov report on ...",
  "ts": "..."
}

======================================================================
20. SOURCES & CITATION HYGIENE (Copyright Safe)
======================================================================
- 장문 전재 금지. 인용은 필요한 최소(단일 인용 <= 25 words).
- 유료/로그인/권한 자료 우회 금지.
- 결과물에는 “근거 URL + 핵심 문장(짧게)”만 남기고, 원문 전체 저장/복제는 기본 OFF.


======================================================================
21. PROFILES & LIMITS (Version-Locked Operational Controls)
======================================================================
v0.4.2.2는 “튜닝 가능한 값”을 반드시 프로파일로 버전 잠금한다.
프로파일 변경은 새 profile_version 발급 + DEC + ChangeHistory를 요구한다.

21.1 Default Profile: PROFILE_DPP_0_4_2_2 (잠금)
- money_unit: USD_MICROS (1 USD = 1,000,000 micros)
- money_display_scale: 4 (API/headers)
- money_rounding: HALF_UP (display-only)
- max_cost_usd_scale_max: 4
- timebox_sec_max: 90
- max_urls_per_run: 30
- fetch_timeout_sec: 10
- fetch_redirect_max_hops: 5
- poll_recommended_interval_ms: 1500
- poll_rate_limit: 60 req/min/tenant (기본; 조정 가능)
- lease_ttl_sec: 120
- lease_heartbeat_sec: 30
- reaper_interval_sec: 30
- reservation_ttl_sec: 3600 (1 hour)
- idempotency_ttl_sec: 2592000 (30 days)
- result_retention_days: 30
- presigned_url_ttl_sec: 600 (10 minutes)
- minimum_fee_formula: max(0.005, 0.02 * reserved_usd) cap 0.10
- max_inline_result_bytes: 262144 (256KB)  (inline=1 옵션에서만)

21.2 Kill Switches (운영 안전장치)
- KILL_FETCH_EXTERNAL: 외부 URL fetch 기능 일괄 off
- KILL_OCR_P2B: 고비용 OCR 모드 off
- KILL_DOCX_ARTIFACT: docx 렌더링 off(성능/보안 이슈 시)
- KILL_POLL_MICROCOST: GET micro-cost 부과 off/on

======================================================================
22. RATE LIMIT & QUOTA HEADERS (Client-Visible Contract)
======================================================================
22.1 RateLimit headers (권장)
- X-RateLimit-Limit: 60
- X-RateLimit-Remaining: 12
- X-RateLimit-Reset: 1700000000 (epoch seconds)
- Retry-After: 2 (429일 때)

22.2 Cost headers (잠금; DEC-4208)
- X-DPP-Cost-Used: "0.0000" (4dp decimal string)
- X-DPP-Cost-Reserved: "0.5000" (POST에서, 4dp decimal string)
- X-DPP-Budget-Remaining: "12.3400" (4dp decimal string)
- X-DPP-Tokens-Consumed: 0 (가능하면)
- NOTE: 내부 ledger는 USD_MICROS(BIGINT)이며, 헤더는 display-only 4dp 문자열이다(DEC-4211).

======================================================================
23. QUEUE IMPLEMENTATION (Single Choice for v0.4.2.2)
======================================================================
DEC-4212: Queue = SQS-Compatible (Production) + LocalStack(Dev)
Decision:
- v0.4.2.2의 작업 큐는 “SQS-Compatible” 인터페이스로 잠금한다.
- Production: AWS SQS (Standard queue)
- Dev/Test: LocalStack SQS (동일 API)
Rationale:
- Redis는 예산/락/리스로 이미 사용되며, 큐까지 Redis에 몰아넣으면 eviction/퍼포먼스 이슈가 “단일 장애점”이 된다.
- SQS는 작업 전달(내구성)과 수평 확장에 강하고, 런 상태/결과는 DB+S3로 분리되어 단순해진다.

Worker Semantics
- 메시지 body: { run_id, attempt:1, enqueued_at }
- visibility timeout: 120s (lease_ttl과 정렬)
- max_receive_count: 3 (DLQ로 이동)
- DLQ 처리: status=FAILED(reason_code=WORKER_CRASHED) + minimum_fee 정산

======================================================================
24. TEST PLAN (Regression & Torture)
======================================================================
24.1 Invariant Tests (필수)
- status=QUEUED/PROCESSING인데 money_state != RESERVED -> FAIL
- terminal인데 money_state not in {SETTLED, REFUNDED} -> FAIL
- PROCESSING인데 lease_token missing -> FAIL

24.2 Concurrency Torture (필수)
- 동일 Idempotency-Key 동시 100 요청 -> run_id 1개, reserve 1번만
- POST 성공 직후 worker crash -> reaper가 timeout 처리, settle 1번만
- reaper와 worker가 동시에 종료 시도 -> DB version(CAS)로 1번만 terminal (DEC-4210)

24.3 Persistence Tests (필수)
- COMPLETED 이후 3시간 뒤 GET -> result_url 재발급 가능
- sha256 검증 성공
- lifecycle 만료 후 owner=410, non-owner=404

24.4 Security Tests (필수)
- owner mismatch run 조회 -> 404
- SSRF private ip redirect -> blocked_logs 기록 + 403/400 정책 응답
- poll 폭탄 -> 429 + Retry-After

======================================================================
25. CHANGE HISTORY
======================================================================
- v0.4.2: B2A Core Specs Integrated (Async runs baseline)
- v0.4.2.1: Hardening Patch Integrated (Persistence/Idempotency/Zombie/AuthZ + 2-phase money-state lock)
- v0.4.2.2: Mandatory Fixes Locked (DB Optimistic Locking + Money Type USD_MICROS)
