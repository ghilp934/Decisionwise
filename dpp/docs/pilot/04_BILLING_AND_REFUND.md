# Billing and Refund

**Decisionproof API - 과금 및 환불 정책**

> ⚠️ **LEGACY / SUPERSEDED by MT0A-1**
>
> 이 문서의 STARTER/₩29,000/Decision Credits(DC)/초과 DC당 ₩39 표현은 **MT0A-1 Surface Sync Patch (2026-04-24)** 에 의해 **customer-facing surface에서 제거/대체**되었습니다. 현재 공개 surface (`dpp/public/pricing.html`, `dpp/public/how-it-works.html`, `dpp/public/llms.txt`, `dpp/public/llms-full.txt`, `README.md`, `dpp/README.md`, `dpp/public/terms.html`, `dpp/docs/SPEC_LOCK_PUBLIC_CONTRACT.md`) 는 Sandbox 한정의 **time-boxed, limit-enforced, fail-closed, no-overage, US$29/30-day access (PayPal)** 모델을 기준으로 합니다.
>
> 본 문서에 서술된 "STARTER ₩29,000/월 + 1,000 DC + 초과 DC당 ₩39" 과금 모델은 customer-facing 공개 surface에 노출되지 않습니다. Decision Credits / DC 용어는 고객-대면 표기에서 금지되며(`SPEC_LOCK_PUBLIC_CONTRACT.md` §7.4, DEC-MT0A-04), 본 파일럿 billing 문서의 DC 기반 과금 표현은 **내부 참조용 legacy**로만 남습니다.
>
> **B2B Design Partner billing**은 별도 계약에 의해 **manual invoice + IBK 기업은행 bank remittance + 세금계산서 (다원세무회계)** 경로로 처리되며, 그 공식 문서화는 MT0A-2 (Pricing Skeleton Lock) 및 MT0B (Revenue Operations Foundation) 에서 완료됩니다. 본 문서는 해당 공식 문서화 이전의 legacy state를 담고 있으므로, customer/partner-facing 문서로 직접 사용해서는 안 됩니다.

---

## 파일럿 과금 방식 (LEGACY — 고객-대면 사용 금지)

### 요금제: STARTER (LEGACY)

**월정액:**
- 기본 요금: ₩29,000/월 (LEGACY; customer-facing surface에서는 US$29 / 30-day Sandbox access로 단일화)
- ~~포함 크레딧: 1,000 DC (Decision Credits)~~ — **REMOVED from customer-facing surface per DEC-MT0A-04**
- ~~초과 사용: DC당 ₩39~~ — **REMOVED; Sandbox는 no overage billing, fail-closed**

**근거 (legacy):** apps/api/dpp_api/pricing/fixtures/pricing_ssot.json (lines 94-100) — 내부 참조용

### Rate Limit (LEGACY)

- 분당 요청 제한: 60 RPM (legacy)
- ~~월간 크레딧 할당: 1,000 DC~~ — **REMOVED per DEC-MT0A-04**
- 초과 시: Block (fail-closed)

**근거 (legacy):** pricing_ssot.json (lines 101-110: limits) — 내부 참조용

### 청구 주기 (B2B Design Partner 경로는 MT0A-2에서 공식화)

- 파일럿 시작일: 계약일
- 청구 주기: 월 단위 (선불) — B2B Design Partner 계약에 한함
- 초과 요금: customer-facing Sandbox에서는 발생하지 않음 (fail-closed). B2B Design Partner 계약에서의 초과/추가 비용은 개별 계약서에 의해 결정.

---

## 환불 및 취소 정책

### SSOT / 판매형태 분기 (필수 체크)

- [ ] **SSOT 우선**: STARTER/₩/DC/초과요금/환불 조건은 `pricing_ssot.json` + 계약서/청구서가 기준. 문서 표기가 다르면 SSOT로 즉시 정정.
- [ ] **판매형태 잠금**: 기본은 **B2B**. **B2C 판매** 시 *청약철회(통상 7일)* 및 *디지털콘텐츠 제공 개시 시 철회 제한 요건(사전 고지·동의/시험사용 등)* 충족 여부를 먼저 체크. :contentReference[oaicite:0]{index=0}
- [ ] **환불창구 1개**: 취소/환불 요청은 `pilot-support@decisionproof.ai` 로만 접수 → 티켓/이메일로 처리 기록 유지.

### B2B 계약 (기본)

**파일럿 중도 해지:**
- 환불 불가 (선불 결제 부분)
- 예외: 서비스 중대 결함 (S0 장애 48시간 이상 지속 등)

**정당한 해지 사유:**
- 서비스 중대 결함으로 사용 불가
- 계약 위반 (당사 귀책)

### 소비자 판매 가능성 고려 (체크리스트)

파일럿 고객이 개인 사업자 또는 소비자인 경우:

- [ ] **전자상거래법 고지**: 파일럿 계약 전 아래 정보 제공
  - 상호/대표자/주소/연락처
  - 재화 등의 가격 및 지급 방법
  - 청약철회 가능 여부 및 제한
- [ ] **청약철회 제한 고지**: 디지털 콘텐츠(API 사용)는 제공 즉시 청약철회 제한 가능
- [ ] **약관 동의 절차**: 계약 체결 전 약관 열람 및 동의 획득

**참고:** 이는 체크리스트이며 법률 자문이 아닙니다. 필요 시 법무팀 검토 권장.

---

## 사용량 추적 및 초과 (Sandbox)

### 비용/사용량 응답 헤더

```bash
# /v1/runs 호출 시 응답 헤더로 확인
curl -v -H "Authorization: Bearer dp_live_your_key_here" \
  https://api.decisionproof.io.kr/v1/runs

# Response Headers:
X-DPP-Cost-Reserved: 10000000  # 예약 비용 (micros)
X-DPP-Cost-Actual: 8500000     # 실제 비용
```

**근거:** apps/api/dpp_api/main.py (lines 70-73: expose_headers)

### 초과 시 동작 (Sandbox, fail-closed)

**Sandbox 플랜:**
- customer-facing DC/초과 DC 과금은 존재하지 않음 (per DEC-MT0A-04)
- Sandbox 한도 초과 시: fail-closed로 거부됨 (`429 Too Many Requests` / 기타 Problem Details)
- 추가 청구 없음 (no overage billing)

**한도 관리:**
- 정기적으로 사용량 모니터링
- 임계값 도달 시 자동 알림 (고객 시스템 구현 권장)

---

## 청구 및 결제

### 청구서 발행

- 발행 시기: 매월 1일
- 내역: 기본 요금 + 초과 요금
- 형식: 세금계산서 (KRW)

### 결제 방법

- 계좌 이체 (기본)
- 카드 결제 (별도 협의)

### 연체 시 조치

- 7일 이내: 독촉 이메일
- 15일 이내: 서비스 일시 중단 경고
- 30일 이상: 서비스 중단 및 계약 해지

---

## 파일럿 특별 조건

### 무료 연장 (조건부)

파일럿 기간 중 **서비스 결함(당사 귀책)**으로 사용 불가 시:
- 결함 발생 일수만큼 무료 연장
- 예: S0 장애 3일 → 파일럿 3일 연장

### 환불 예외

다음의 경우 일부 환불 가능:
- 서비스 중대 결함(S0)이 30일 중 7일 이상 지속
- 계약 내용과 실제 기능 불일치 (당사 귀책)

**절차:**
1. 서면 요청 (pilot-support@decisionproof.ai)
2. 증빙 제출 (증거 로그, request_id 등)
3. 검토 후 7영업일 내 회신

---

## 다음 단계

1. 사용량/비용 응답 헤더 (X-DPP-Cost-Reserved / X-DPP-Cost-Actual) 추적 방법 숙지
2. B2B Design Partner 계약 시: 청구서 발행일 확인 (계약에 따름)
3. Sandbox 한도 근접 시 fail-closed 방지를 위한 자사 시스템 모니터링 설정

---

## MT0A-1 정렬 주: customer-facing 문서가 아님

본 문서는 **내부 파일럿 legacy state**를 담고 있습니다. 고객/파트너에게 공개하기 전에는 아래 공식 문서를 참조해야 합니다:

- Customer-facing pricing: `dpp/public/pricing.html`
- MT0A-1 SSOT DEC: `_DP_v1_0/open_ssot_decisions_v0.2_redteam.md`
- SPEC_LOCK (MT0A-1 aligned): `dpp/docs/SPEC_LOCK_PUBLIC_CONTRACT.md`
- B2B Design Partner billing path (MT0A-2/MT0B 예정): Billing Path A = manual invoice + IBK 기업은행 + 세금계산서 (다원세무회계)
