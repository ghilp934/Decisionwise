# Decisionproof v0.4 RC Acceptance Criteria (RC_ACCEPTANCE.md)

Doc ID: DP-RC-ACCEPT-v0.4
Status: SPEC LOCK (Audited Patch A1 Applied)
Owner: Sung
Last Updated: 2026-02-14 (Asia/Seoul)

────────────────────────────────────────
0) RC 선언의 의미(정의)
Decisionproof v0.4 RC는 “코드가 돌아간다”가 아니라,
외부 고객/에이전트가 문서만 읽고 호출해도 계약(Contract)이 깨지지 않고,
과금/정산 불변식이 테스트로 증명되며,
문서·스키마·실동작이 단일화된 상태를 의미한다.

RC는 파일럿(21D) 투입 가능한 “Release Candidate”이며,
RC 통과는 아래 게이트(RC-0~RC-8)의 PASS를 의미한다.

────────────────────────────────────────
1) 범위(Scope) / 비범위(Non-Goals)

[Scope]
- MT-1 ~ MT-3 + 기타 마이너 패치 포함 코드베이스
- 서비스/프로젝트 명칭: Decisionproof 로 통일(표기/문서/메타데이터/스펙)
- 외부 계약(Contract) 항목: Auth, Error Format, RateLimit Headers, Docs Endpoints, Pricing SSOT
- Worker/Reaper/Receipt-Reconcile 포함(정산 불변식 관련 경로)

[Non-Goals]
- 기능 확장(새 API/새 플랜 추가)은 RC 이후(별도 DEC/스프린트)
- 성능 최적화(대규모 부하 최적화)는 RC 이후(파일럿 데이터 기반)
- UI/대시보드 완성도는 RC 필수조건이 아님(필요 시 최소 관측만)

────────────────────────────────────────
2) RC 게이트 요약(필수 PASS)

RC-0 Spec Lock (RC 정의/기준 잠금)
RC-1 Contract: Auth + Docs + OpenAPI 정합(단일화)
RC-2 Contract: Error Format (Problem Details) 정합(단일화)
RC-3 Contract: RateLimit Headers 정합(단일화)
RC-4 Billing/Settlement Invariants (Reserve→Finalize→Reconcile) 테스트 증명
RC-5 Release Hygiene + API Inventory + Secrets Scanning(오염/노출/비밀정보 제거)
RC-6 Observability Minimum(추적 가능성/지표)
RC-7 Staging E2E Gate (10 케이스) PASS + Rollback Runbook
RC-8 RC 선언 패킷(Release Notes + Pilot Ready) 완료

RC 선언 조건: 위 9개 모두 PASS + P0 결함 0개

────────────────────────────────────────
3) P0 결함 정의(1개라도 존재하면 RC FAIL)

P0-AuthMismatch:
- Quickstart / function-calling spec / OpenAPI / 실제 구현의 인증 방식이 불일치

P0-ErrorFormatMismatch:
- 401/403/402/409/422/429 경로에서 표준 에러 포맷이 혼재(예: {detail:...} 남음)

P0-RateLimitMismatch:
- RateLimit 헤더 체계가 혼재(X-RateLimit-*와 RateLimit-* 동시 사용 등)
- 429 시 Retry-After 헤더 누락

P0-BillingUnsafeDefault:
- 설정 누락/예외 케이스에서 청구(billable)가 “안전하지 않은 기본값”으로 발생 가능

P0-TraceIdentifierLeak:
- Problem Details의 instance/request_id 등에 내부 DB PK(자동증가 ID 등) 또는 추정 가능한 식별자가 노출됨
- instance는 “opaque identifier” 원칙을 위반하면 FAIL

P0-ReleaseContamination:
- 배포 산출물에 __pycache__/pyc/.coverage/backup 등 개발 부산물 포함
- 외부 노출 API 인벤토리(OpenAPI) 밖의 엔드포인트가 운영에서 노출

P0-SecretsLeak:
- 배포 산출물/리포지토리에 .env, 하드코딩 API Key/Token, AWS Credential 등 비밀정보 포함

────────────────────────────────────────
4) 게이트별 상세 기준(Deliverable + Pass/Fail)

RC-0) Spec Lock
[Deliverable]
- 본 문서 RC_ACCEPTANCE.md “잠금” 완료(이후 변경은 DEC로만)

[PASS]
- RC 정의/범위/게이트/P0 정의가 확정
- 변경관리 규칙(아래 8번) 포함

[FAIL]
- “문서/예시/스키마 vs 실동작” 불일치 허용 문구가 존재하거나,
  게이트 기준이 모호해 재현성이 떨어짐

────────────────────────────────────────
RC-1) Contract 단일화: Auth + Docs + OpenAPI
[Deliverable]
- /.well-known/openapi.json
- /public/docs/quickstart.md
- /docs/function-calling-specs.json
- (선택) /docs/auth.md

[PASS]
- 인증 방식이 “단 하나”로 통일되어 문서/예시/구현이 1:1 일치
- Quickstart의 curl 예시 1개가 그대로 실행되어 200/201 응답
- OpenAPI securitySchemes가 선택한 방식과 정확히 일치

[FAIL]
- 문서에는 X인데 구현은 Y로 받는 케이스 존재
- 예시 실행 불가(401/403/422 등) 또는 OpenAPI 표기가 다름

────────────────────────────────────────
RC-2) Contract 단일화: Error Format (Problem Details)
[Deliverable]
- /docs/problem-types.md
- API가 401/403/402/409/422/429에서 application/problem+json 반환

[PASS]
- 위 상태코드 최소 세트에서 아래 필드 포함:
  type, title, status, detail, instance
- 429에는 Retry-After 헤더가 반드시 포함
- instance에 request_id 또는 run_id 등 추적 키 포함(로그 상관관계 가능)

[PASS - Addendum: instance 안전 규칙]
- instance는 내부 DB PK/자동증가 ID/추정 가능한 숫자열을 절대 사용하지 않는다.
- instance는 Opaque Trace ID(예: UUIDv4/ULID)를 사용하며, 필요 시 URN 형태 권장:
  예) "instance": "urn:decisionproof:trace:01HS...ULID"
- instance는 서버에 의미가 있을 수 있으나, 클라이언트 관점에서는 “opaque”여야 한다.

[FAIL]
- {detail: "..."} 같은 비표준 에러가 P0 경로에 1개라도 존재
- 429에 Retry-After 누락
- instance에 내부 PK/추정 가능한 식별자 노출

────────────────────────────────────────
RC-3) Contract 단일화: RateLimit Headers
[Deliverable]
- /docs/rate-limits.md
- 응답 헤더: RateLimit-Policy, RateLimit (+ 429시 Retry-After)

[PASS]
- RateLimit 헤더 체계가 단일화(표준 체계 1개만 사용)
- 문서(/docs/rate-limits.md)와 실제 헤더가 1:1 일치
- 클라이언트가 헤더만 보고 백오프 가능(429 핸들링 가능)

[FAIL]
- X-RateLimit-*와 RateLimit-* 혼재
- 429 시 Retry-After 누락 또는 문서와 헤더 불일치

────────────────────────────────────────
RC-4) Billing/Settlement 불변식(테스트로 “증명”)
[Deliverable]
- 최소 테스트 4개(유닛/통합 어느 쪽이든, CI에서 자동 실행)
  T1: 400/422는 절대 billable 아님 (No Charge on Validation Fail)
  T2: finalize 멱등 + 단일 차감 보장 (Idempotent Finalize + Single Debit)
      - 동일 reserve_id/run_id에 finalize를 N번 호출해도 "잔액 차감/원장 반영"은 1회만 발생
  T3: reconcile이 미완료/유실 상태를 수습(최소 1회전 증명)
  T4: 동시성(Concurrency) - Insufficient Funds 레이스 방어
      - 잔액이 부족한 상황에서 병렬 reserve/finalize 요청이 발생해도:
        (a) 잔액이 음수로 내려가지 않음
        (b) 허용 한도 초과 청구/차감이 발생하지 않음
        (c) 실패는 402(또는 정책상 정의한 코드) + Problem Details로 귀결됨

[PASS]
- billable 기본값이 안전 방향(미청구)이며, 동시성 테스트(Concurrency Test)까지 통과한다.
- finalize 멱등성은 “요청 재시도에서 에러가 안 남”이 아니라,
  “원장/잔액 side-effect가 1회만 발생”으로 증명된다.
- reconcile이 최소 1개 케이스에서 기대 동작을 증명한다.
- 실패 시 에러는 Problem Details로 반환되어 재현/포렌식이 가능하다.

[FAIL]
- 설정 누락/예외가 청구로 이어질 가능성 존재
- finalize 중복 호출로 잔액 2중 차감 가능성 존재
- 경쟁 상태에서 잔액 음수/오버드래프트 가능성 존재

────────────────────────────────────────
RC-5) Release Hygiene + API Inventory + Secrets Scanning
[Deliverable]
- 배포 산출물에서 개발 부산물 제거
  (__pycache__, *.pyc, .coverage, *.backup 등)
- 운영 노출 API 인벤토리 1페이지(API Inventory)
- Sensitive Data Scan Report (Secrets Scanning)
  - 스캔 대상: 배포 산출물 + 리포지토리(또는 빌드 아티팩트)
  - 탐지 대상 예: .env, 하드코딩된 API Key/Token, AWS Credentials 등
  - 결과: 발견 0건 또는 발견 시 “폐기+회전+재발방지 조치” 기록

[PASS]
- 배포물 오염 0개
- OpenAPI에 없는 운영 엔드포인트 노출 0개
- Secrets Scanning에서 “배포 산출물 내 비밀정보 포함” 0건

[FAIL]
- 디버그/레거시 엔드포인트 노출
- 배포 산출물 오염(위 파일/폴더) 존재
- 비밀정보(.env/키/토큰/자격증명) 포함

────────────────────────────────────────
RC-6) Observability Minimum
[Deliverable]
- 구조화 로그(최소 필드)
  request_id, run_id, plan_key, budget_decision, status_code
- 핵심 지표 3개(계산 가능해야 함)
  SLI1: 5xx rate
  SLI2: 429 rate
  SLI3: TTFC(첫 성공 호출까지 시간)

[PASS]
- 장애 시 request_id/run_id로 5분 내 추적 가능
- 지표가 최소 단위로라도 산출 가능

[FAIL]
- 장애가 나면 추적 불가(상관관계 키 누락)
- 429/5xx가 발생해도 관측 불가

────────────────────────────────────────
RC-7) Staging E2E Gate (10 케이스) + Rollback Runbook
[Deliverable]
- 스테이징에서 재현 가능한 E2E 시나리오 10개(스크립트/문서화)
  (해피패스 + 422 + 429 + 워커/리퍼 경합 + 큐 지연 포함)
- Rollback Runbook (링크 또는 파일)
  - 실행 주체(Owner/On-call): 누구
  - 실행 방식: Manual / Automated 중 명시
  - 실행 명령어: 어떤 명령(또는 스크립트)
  - 목표 시간: N분 이내(예: 10분 이내)로 복구 가능한 절차
  - 롤백 후 검증 체크리스트(최소 3항)

[PASS]
- 10개 전부 PASS
- FAIL 발생 시 롤백/킬스위치 절차가 “수동/자동 중 무엇인지” 명시되어 있으며,
  Runbook에 따라 N분 내 실행 가능함이 재현 가능한 수준으로 문서화되어 있다.

[FAIL]
- run 유실 / 상태 전이 꼬임 / 예산 음수 가능성 등 불변식 위반
- 429/422가 계약대로 동작하지 않음
- “즉시 롤백”이 구체 명령/주체/시간 목표 없이 선언만 존재

────────────────────────────────────────
RC-8) RC 선언 패킷(외부 배포용)
[Deliverable]
- RELEASE_NOTES_v0.4_RC.md
  (변경점 / Known Issues / 롤백 플랜 / 호환성 노트)
- PILOT_READY.md
  (21D 파일럿 투입 체크 1페이지)

[PASS]
- 외부 공유 가능한 “정리된 상태”로 2개 문서 완성
- Known Issues는 “회피/완화/대응”이 함께 적혀 있음

[FAIL]
- 릴리즈 설명이 모호하거나, 파일럿 투입 기준이 불명확

────────────────────────────────────────
5) Evidence Pack (RC 통과 증빙 묶음)
RC 통과 시 아래 자료를 하나의 폴더/아카이브로 묶어 보관한다.

- RC_ACCEPTANCE.md (본 문서)
- /.well-known/openapi.json (스테이징/프로덕션 스냅샷)
- /docs/function-calling-specs.json
- /pricing/ssot.json (+ /docs/pricing-ssot.md)
- /docs/problem-types.md
- /docs/rate-limits.md
- 테스트 리포트(최소 4개) + E2E 10케이스 결과
- API Inventory 1페이지
- Sensitive Data Scan Report (Secrets Scanning)
- Rollback Runbook (Manual/Automated 명시)
- RELEASE_NOTES_v0.4_RC.md
- PILOT_READY.md

────────────────────────────────────────
6) 변경관리(Change Control)
- 본 문서 및 RC 게이트 기준 변경은 DEC(Decision Record)로만 수행한다.
- RC 기간 중 “새 기능 추가”는 금지(Non-Goals 범위로 이관).
- 예외가 필요하면 “RC 선언 연기”가 기본값이며,
  예외 승인 시 영향 범위/롤백/테스트 추가가 반드시 포함되어야 한다.

────────────────────────────────────────
7) 롤백 플랜(Rollback Plan) 최소 조건
- Level 1: API만 롤백(Worker/DB 유지)
- Level 2: API+Worker 롤백(마이그레이션 영향 없을 때)
- Level 3: 전체 롤백(데이터/스키마 영향 포함 시, 사전 절차 필요)

각 레벨별로 “트리거 조건(예: 5xx>1% 지속 10분, 429 급증 등)”과
“복구 후 검증 체크리스트(3항목 이상)”를 RELEASE_NOTES에 포함한다.

────────────────────────────────────────
8) 참고 표준(Reference Standards)
아래 URL들은 문서 참조용이며, RC 선언 시 준수/근거 표준으로 사용한다.

```text
RFC 9457: Problem Details for HTTP APIs
https://www.rfc-editor.org/rfc/rfc9457.html

RateLimit header fields for HTTP (IETF draft; RateLimit-Policy / RateLimit)
https://datatracker.ietf.org/doc/draft-ietf-httpapi-ratelimit-headers/

OWASP API Security Top 10 (2023)
https://owasp.org/API-Security/editions/2023/en/0x11-t10/

OWASP API9:2023 - Improper Inventory Management
https://owasp.org/API-Security/editions/2023/en/0xa9-improper-inventory-management/

OpenAPI Specification (v3.1)
https://swagger.io/specification/

OWASP Secrets Management Cheat Sheet
https://cheatsheetseries.owasp.org/cheatsheets/Secrets_Management_Cheat_Sheet.html

GitHub Docs: About secret scanning
https://docs.github.com/code-security/secret-scanning/about-secret-scanning

AWS Well-Architected (Operational Excellence): Automate testing and rollback
https://docs.aws.amazon.com/wellarchitected/latest/operational-excellence-pillar/ops_mit_deploy_risks_auto_testing_and_rollback.html

Google CRE Life Lessons: Reliable releases and rollbacks
https://cloud.google.com/blog/products/gcp/reliable-releases-and-rollbacks-cre-life-lessons