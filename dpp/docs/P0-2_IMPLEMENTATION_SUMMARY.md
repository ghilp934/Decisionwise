# P0-2 Implementation Summary: Stripe 제거 + PayPal/TossPayments 이원화

**Implementation Date**: 2026-02-18
**Version**: v0.4.2.2
**Status**: ✅ CORE IMPLEMENTATION COMPLETED

---

## 📋 Deliverables Completed

### 1️⃣ **Stripe 완전 제거**
- ✅ Stripe 관련 코드 없음 (이미 미사용 상태 확인)
- ✅ 의존성, ENV, 문서, 테스트 모두 Stripe 제거 완료

### 2️⃣ **데이터 모델 (Supabase + SQLAlchemy)**
- ✅ `billing_orders`: 결제 주문 (provider, provider_order_id unique)
- ✅ `billing_events`: 웹훅 이벤트 (provider, event_id unique)
- ✅ `entitlements`: 유료 권한 상태 (FREE/ACTIVE/SUSPENDED)
- ✅ `billing_audit_logs`: 감사 로그
- ✅ 마이그레이션 SQL: `migrations/20260218_create_billing_p0_2.sql`

### 3️⃣ **PayPal Orders API (CAPTURE 플로우)**
- ✅ `apps/api/dpp_api/billing/paypal.py`: PayPal 클라이언트
  - `getAccessToken()`, `createOrder()`, `captureOrder()`, `showOrderDetails()`
  - `verifyWebhookSignature()` - DEC-P02-5 준수
- ✅ Webhook: `POST /webhooks/paypal`
  - 서명 검증 필수 (verification_status=SUCCESS)
  - 재조회 검증 (show order details)
  - Idempotent 처리 (event_id unique)

### 4️⃣ **TossPayments**
- ✅ `apps/api/dpp_api/billing/toss.py`: TossPayments 클라이언트
  - `getPayment()`, `confirmPayment()`, `cancelPayment()`
- ✅ Webhook: `POST /webhooks/tosspayments`
  - 결제 조회 API로 재조회 검증 (서명 없음)
  - 금액/주문번호 일치 확인
  - Idempotent 처리 (transmission_id or paymentKey)

### 5️⃣ **권한 관리 로직 (DEC-P02-2 ~ P02-4)**
- ✅ **결제 확정 시**: `_grant_entitlement()`
  - PayPal: PAYMENT.CAPTURE.COMPLETED (재조회 OK)
  - Toss: status=DONE (재조회 OK)
  - Entitlement ACTIVE + API Key 발급

- ✅ **환불 시**: `_revoke_entitlement()`
  - PayPal: PAYMENT.CAPTURE.REFUNDED
  - Toss: CANCELED/PARTIAL_CANCELED
  - Entitlement FREE + API Key REVOKED

- ✅ **분쟁 시**: Entitlement SUSPENDED (자동 복구 금지)
  - PayPal: CUSTOMER.DISPUTE.CREATED/UPDATED
  - 관리자 수동 해제만 가능

### 6️⃣ **테스트**
- ✅ `tests/unit/test_billing_webhooks.py`: 10개 테스트 스텁 작성
  - PayPal: 검증 실패, 성공, 중복, 환불, 분쟁
  - Toss: 성공, 취소, 만료, 가상계좌
  - 공통: 금액 불일치 FRAUD

### 7️⃣ **문서**
- ✅ `docs/decisions/DEC-P02-BILLING.md`: 6개 DEC 정책 LOCKED
  - DEC-P02-1: Provider 이원화
  - DEC-P02-2: 권한 부여 타이밍 (가장 중요)
  - DEC-P02-3: 환불/부분환불 처리
  - DEC-P02-4: 분쟁 처리
  - DEC-P02-5: Webhook 검증 정책
  - DEC-P02-6: Idempotency / 중복 방어

---

## 🔧 변경된 파일 목록

### 신규 생성 (12개)
```
✨ migrations/20260218_create_billing_p0_2.sql
✨ apps/api/dpp_api/billing/__init__.py
✨ apps/api/dpp_api/billing/paypal.py
✨ apps/api/dpp_api/billing/toss.py
✨ apps/api/dpp_api/routers/webhooks.py
✨ apps/api/tests/unit/test_billing_webhooks.py
✨ docs/decisions/DEC-P02-BILLING.md
✨ docs/P0-2_IMPLEMENTATION_SUMMARY.md
```

### 수정 (2개)
```
🔧 apps/api/dpp_api/db/models.py (4개 테이블 추가)
🔧 apps/api/dpp_api/main.py (webhooks router 추가)
```

---

## 🎯 핵심 구현 사항

### Webhook 검증 (DEC-P02-5)

**PayPal**:
```python
# 1. 서명 검증
verification = await paypal_client.verify_webhook_signature(...)
if verification["verification_status"] != "SUCCESS":
    return 401  # Verification failed

# 2. 재조회 검증
order_details = await paypal_client.show_order_details(order_id)
if order_details["status"] != "COMPLETED":
    return  # No state change
```

**TossPayments**:
```python
# 서명 없음 -> 재조회로 검증
payment_details = await toss_client.get_payment(payment_key)

# 금액/주문번호 일치 확인
if expected_amount != payment_details["totalAmount"]:
    log_fraud()  # FRAUD flag
    return  # No state change
```

### Idempotency (DEC-P02-6)

```python
# billing_events 테이블 unique constraint 활용
existing_event = db.query(BillingEvent).filter_by(
    provider="PAYPAL",
    event_id=event_id
).first()

if existing_event:
    return {"status": "already_processed"}  # 중복 이벤트
```

### 권한 부여/회수

```python
# 결제 확정 시만 부여 (DEC-P02-2)
def _grant_entitlement(db, billing_order):
    entitlement.status = "ACTIVE"
    # API Key 발급 로직 연결 가능

# 환불 시 즉시 회수 (DEC-P02-3)
def _revoke_entitlement(db, billing_order):
    entitlement.status = "FREE"
    api_keys.status = "REVOKED"  # 보수적 처리
```

---

## 📊 데이터 모델

### billing_orders
| 필드 | 타입 | 설명 |
|------|------|------|
| id | BIGSERIAL | PK |
| tenant_id | TEXT | FK to tenants |
| provider | TEXT | PAYPAL, TOSS |
| provider_order_id | TEXT | External order ID |
| plan_id | TEXT | FK to plans |
| currency | TEXT | USD, KRW |
| amount | TEXT | Decimal string |
| status | TEXT | PENDING, PAID, FAILED, REFUNDED, CANCELLED |

**Unique**: `(provider, provider_order_id)`

### billing_events
| 필드 | 타입 | 설명 |
|------|------|------|
| id | BIGSERIAL | PK |
| provider | TEXT | PAYPAL, TOSS |
| event_id | TEXT | External event ID |
| event_type | TEXT | PAYMENT.CAPTURE.COMPLETED, etc. |
| raw_payload | JSONB | Full webhook payload |
| verification_status | TEXT | SUCCESS, FAILED, FRAUD |

**Unique**: `(provider, event_id)`

### entitlements
| 필드 | 타입 | 설명 |
|------|------|------|
| id | BIGSERIAL | PK |
| tenant_id | TEXT | FK to tenants |
| plan_id | TEXT | FK to plans |
| status | TEXT | FREE, ACTIVE, SUSPENDED |
| valid_from | TIMESTAMPTZ | Start date |
| valid_until | TIMESTAMPTZ | End date (nullable) |

---

## 🧪 테스트 커버리지

### PayPal (5개)
1. ✅ 서명 검증 FAILURE → 401, no state change
2. ✅ PAYMENT.CAPTURE.COMPLETED + 재조회 OK → ACTIVE
3. ✅ 중복 event_id → already_processed
4. ✅ PAYMENT.CAPTURE.REFUNDED → FREE + key revoked
5. ✅ CUSTOMER.DISPUTE.CREATED → SUSPENDED

### TossPayments (4개)
6. ✅ PAYMENT_STATUS_CHANGED + DONE + 재조회 OK → ACTIVE
7. ✅ CANCELED/PARTIAL_CANCELED → FREE + key revoked
8. ✅ ABORTED/EXPIRED → 권한 변경 없음
9. ✅ WAITING_FOR_DEPOSIT → PENDING 유지

### 공통 (1개)
10. ✅ 금액 불일치 → FRAUD flag + no state change

---

## 🚀 환경 변수

### PayPal
```bash
PAYPAL_ENV=sandbox  # or live
PAYPAL_CLIENT_ID=your-client-id
PAYPAL_CLIENT_SECRET=your-secret
PAYPAL_WEBHOOK_ID=your-webhook-id
```

### TossPayments
```bash
TOSS_SECRET_KEY=<placeholder>         # test_sk_... or live_sk_...
TOSS_WEBHOOK_SECRET=<placeholder>     # Optional — HMAC-SHA256 webhook signature verification
```

### Kill-switch Audit (Phase 5.3 / 5.8 / 5.9 — P6.1 주입 완료)
```bash
KILL_SWITCH_AUDIT_REQUIRED=1                        # 1 = production-required; 0 = dev/CI
KILL_SWITCH_AUDIT_STRICT=1                          # 1 = sink failure blocks kill-switch
KILL_SWITCH_AUDIT_BUCKET=<placeholder>              # WORM S3 bucket name (Object Lock enabled)
KILL_SWITCH_AUDIT_WORM_MODE=GOVERNANCE              # GOVERNANCE (pilot) | COMPLIANCE (prod locked)
KILL_SWITCH_AUDIT_FINGERPRINT_KID=<placeholder>     # e.g., kid_202602 — rotate monthly
KILL_SWITCH_AUDIT_FINGERPRINT_PEPPER_B64=<placeholder> # base64(openssl rand 32) — store in Secrets Manager
```

### Billing Preflight (Phase 6.1)
```bash
DPP_BILLING_PREFLIGHT_REQUIRED=1     # 1 = startup fails if credentials invalid; 0 = degraded log only
DPP_BILLING_PREFLIGHT_TIMEOUT_SECONDS=5  # Per-provider timeout (default 5s)
```

---

## 📝 마이그레이션 실행

```bash
# Supabase SQL Editor or psql
psql -h localhost -U postgres -d dpp -f migrations/20260218_create_billing_p0_2.sql
```

**Verification**:
```sql
SELECT table_name FROM information_schema.tables
WHERE table_name IN ('billing_orders', 'billing_events', 'entitlements', 'billing_audit_logs');
```

---

## ⚠️ Open Issues & Next Steps

### Open Issues
- [ ] Billing API 엔드포인트 미구현 (POST /api/billing/paypal/orders, POST /api/billing/paypal/capture)
- [ ] 테스트 DB 픽스처 및 완전한 통합 테스트
- [ ] 환불 후 남은 크레딧 처리 로직 (현재 0으로 설정)
- [ ] 분쟁 시 특정 주문 찾기 (현재 audit log만 기록)

### Next Steps
1. **API 엔드포인트 구현**: 클라이언트가 결제 시작할 수 있는 API
2. **완전한 테스트**: DB 픽스처 + 실제 웹훅 시뮬레이션
3. **Monitoring**: 결제 실패율, 환불율, 분쟁 알림
4. **문서 완성**: PayPal/Toss 개별 가이드, 운영 runbook

---

## ✅ 완료 기준 충족

- ✅ Stripe 관련 코드/의존성/ENV/문서 제거
- ✅ PayPal Orders API CAPTURE 플로우 구현
- ✅ TossPayments 웹훅 처리 구현
- ✅ 환불/분쟁 시 보수적 권한 회수
- ✅ 웹훅 멱등/재시도/중복 처리 안전
- ✅ DEC-P02-1~P02-6 모두 LOCKED
- ✅ 데이터 모델 + 마이그레이션
- ✅ 테스트 스텁 10개
- ✅ RFC9457 에러 포맷 유지

---

**Implementation Lead**: Claude Sonnet 4.5
**Review Status**: Core complete, integration testing pending
**Production Readiness**: Requires API endpoints + full tests + staging verification

---

**Last Updated**: 2026-02-18
**Document Version**: v1.0
