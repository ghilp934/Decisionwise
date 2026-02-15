# Paid Pilot Kickoff Packet

**Decisionproof API Platform v0.4.2.2 - Paid Pilot Program**

문서 버전: 2026-02-15
대상: 파일럿 참여 고객

---

## 이 패킷으로 무엇을 하나요?

이 Paid Pilot Kickoff Packet은 Decisionproof API Platform의 **유료 파일럿 프로그램**에 참여하시는 고객을 위한 **온보딩부터 오프보딩까지 전체 과정**을 안내합니다.

### 패킷 구성

| 문서 | 내용 | 대상 |
|------|------|------|
| `01_ONBOARDING_CHECKLIST.md` | 온보딩 체크리스트 (계정/토큰/첫 호출) | 기술 담당자 |
| `02_QUICKSTART_FOR_PILOT.md` | API 빠른 시작 가이드 (curl 예시) | 개발자 |
| `03_SUPPORT_AND_ESCALATION.md` | 지원 채널 및 장애 대응 | 운영 담당자 |
| `04_BILLING_AND_REFUND.md` | 과금/환불/변경 정책 | 계약 담당자 |
| `05_SECURITY_PRIVACY_BASELINE.md` | 보안 및 개인정보 기준 | 보안/컴플라이언스 |
| `06_ACCEPTABLE_USE_POLICY.md` | 허용 사용 정책 (금지행위) | 전체 이용자 |
| `07_AI_DISCLOSURE.md` | 생성형 AI 사용 고지 | 법무/마케팅 |
| `08_OFFBOARDING_AND_DATA_RETENTION.md` | 종료 절차 및 데이터 보관 | 운영/보안 담당자 |
| `09_CHANGELOG_AND_CONTACTS.md` | 변경 로그 및 연락처 | 전체 |

---

## 파일럿 프로그램 개요

### 목적

Decisionproof API Platform의 **실제 업무 환경(Staging)**에서 기능, 성능, 안정성을 검증하고, 프로덕션 도입 가능성을 평가합니다.

### 기간 및 범위

**기간:**
- 파일럿 시작일: [계약서 참조]
- 파일럿 종료일: [계약서 참조]
- 기본 기간: 1개월 (연장 가능, 별도 협의)

**범위:**
- **환경**: Staging 환경 전용
- **기능**: Decisionproof API v0.4.2.2 전체 기능
  - Decision Pack 실행 API (`/v1/runs`)
  - 헬스 체크 (`/health`, `/readyz`)
  - OpenAPI 문서 (`.well-known/openapi.json`)
- **요금제**: STARTER 플랜 (월 ₩29,000, 1,000 DC 포함)
  - 초과 사용: DC당 ₩39
  - Rate Limit: 60 RPM
- **지원**: 영업시간 내 이메일/슬랙 지원 (응답 목표: 4시간)

**제외 범위:**
- ✗ Production 환경 접근 (파일럿 종료 후 별도 승인 필요)
- ✗ 24/7 긴급 지원 (영업시간 외 지원 제외)
- ✗ SLA 보장 (파일럿 기간 중 SLA 적용 제외)

---

## 지원 및 성공 기준

### 지원 제공

**채널:**
- 이메일: pilot-support@decisionproof.ai
- Slack: #dpp-pilot-support (초대 링크 별도 제공)
- 응급: [담당자 연락처 - `09_CHANGELOG_AND_CONTACTS.md` 참조]

**운영 시간:**
- 월~금 09:00~18:00 (KST)
- 공휴일 제외

**응답 목표:**
- S0 (서비스 중단): 1시간 (최선 노력)
- S1 (주요 기능 오류): 4시간
- S2 (일반 문의): 1영업일
- S3 (기능 요청): 협의

### 성공 기준 (측정 가능)

파일럿 종료 시 아래 기준으로 성공 여부를 평가합니다:

| 항목 | 목표 | 측정 방법 |
|------|------|----------|
| **기능 검증** | 핵심 시나리오 10개 성공 | 고객 제출 테스트 결과 |
| **성능 검증** | API 응답시간 p95 < 500ms | 모니터링 로그 |
| **안정성 검증** | Uptime > 99% (파일럿 기간) | 모니터링 로그 |
| **통합 검증** | 고객 시스템 연동 완료 | 고객 확인서 |
| **지원 만족도** | 지원 응답 적시성 80% 이상 | 지원 티켓 로그 |

**성공 시:**
- Production 환경 승인 절차 안내
- 정식 계약 전환 조건 제시

**미달 시:**
- 원인 분석 및 개선 계획 수립
- 파일럿 연장 또는 종료 협의

---

## 빠른 시작 (3단계)

### 1단계: 온보딩 체크리스트 완료

`01_ONBOARDING_CHECKLIST.md`를 따라 계정/토큰 발급 및 네트워크 설정을 완료하세요.

### 2단계: 첫 API 호출

`02_QUICKSTART_FOR_PILOT.md`의 curl 예시로 `/health` 엔드포인트를 호출하세요.

```bash
curl https://staging-api.decisionproof.ai/health
```

**예상 응답:**
```json
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

### 3단계: 실제 Decision Run 호출

Bearer 토큰을 사용하여 `/v1/runs` 엔드포인트로 첫 실행을 생성하세요 (상세: `02_QUICKSTART_FOR_PILOT.md`).

---

## 중요 안내사항

### Staging vs. Production

- **이 패킷의 모든 예시는 Staging 환경 기준**입니다.
- Production 환경 사용은 파일럿 종료 후 **별도 승인 절차** 필요.
- Staging과 Production의 엔드포인트/토큰/설정은 **완전히 분리**됨.

### 생성형 AI 사용 고지

본 서비스는 **생성형 AI 기술**을 사용합니다. 서비스 산출물 사용 시 고지 권장사항은 `07_AI_DISCLOSURE.md`를 참조하세요.

### 개인정보 처리

서비스 이용 중 개인정보가 처리될 수 있습니다. 처리 범위 및 보안 기준은 `05_SECURITY_PRIVACY_BASELINE.md`를 참조하세요.

### 허용 사용 정책

서비스 남용, 공격, 키 공유 등은 금지됩니다. 상세 금지행위는 `06_ACCEPTABLE_USE_POLICY.md`를 참조하세요.

---

## 문의 및 피드백

**파일럿 담당자:**
- 이름: [담당자명]
- 이메일: pilot-support@decisionproof.ai
- Slack: #dpp-pilot-support

**긴급 연락:**
- [09_CHANGELOG_AND_CONTACTS.md 참조]

**문서 업데이트:**
- 최종 수정일: 2026-02-15
- 버전: v0.4.2.2
- 변경 로그: `09_CHANGELOG_AND_CONTACTS.md` 참조

---

**다음 단계:**

1. ✅ `01_ONBOARDING_CHECKLIST.md` 읽고 체크리스트 완료
2. ✅ `02_QUICKSTART_FOR_PILOT.md`로 첫 API 호출
3. ✅ `03_SUPPORT_AND_ESCALATION.md`로 지원 채널 확인
4. ✅ 나머지 문서 숙지 (보안/컴플라이언스/정책)

**환영합니다! Decisionproof Paid Pilot에 참여해주셔서 감사합니다.** 🎉
