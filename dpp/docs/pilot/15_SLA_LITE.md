# SLA-lite (Design Partner / Pilot)

**Decisionproof Design Partner (Paid Pilot) — SLA-lite (Best Effort)**

문서 버전: 2026-04-24 (MT0A-1 Aligned)
이전 버전: 2026-02-16

---

## MT0A-1 정렬 요약

- 고객-대면 심각도는 **Sev1 / Sev2 / Sev3 / Sev4** 로 통일합니다 (기존 P0 / S1 / S2 / S3 표기 superseded).
- 본 문서는 **Design Partner (B2B) track 전용**입니다. **Sandbox (paid private beta)** 의 고객 지원은 별개 트랙으로, `terms.html`, `contact.html`, `security.html` 에 정의된 "Sandbox: email-based, best effort, target first response within 1 business day, no uptime SLA" 를 따릅니다.
- 본 문서의 모든 응답 목표는 **Best Effort** 이며, **최종 SLA는 서명된 파일럿 계약서 / 주문서(Order Form)** 에 의해 확정됩니다.
- Sev2의 "8시간" 이전에 S1 "2시간" 이 있던 기존 표기는 MT0A-1 DEC-MT0A-06 에 따라 Sev1 4h / Sev2 8h / Sev3 1영업일 / Sev4 2영업일 로 재정렬했습니다.

---

## 목적

본 문서는 Decisionproof Design Partner (파일럿) 단계에서의 **서비스 수준 목표(SLO/SLA-lite)** 를 "최선 노력(Best Effort)" 기준으로 정리합니다.

- Design Partner 파일럿 단계에서 Decisionproof는 24/7 상시 대응을 기본 제공하지 않습니다.
- 본 문서는 Design Partner 고객 기대치 정렬을 위한 문서이며, 최종 SLA는 별도 서명 계약으로 확정합니다.
- Sandbox 고객에게는 본 Design Partner Sev1-Sev4 응답 목표가 **적용되지 않습니다**. Sandbox 지원 조건은 Terms of Use 및 Contact 페이지를 참조하십시오.

---

## 1) 지원 시간 (Design Partner)

- 정규 지원: 월~금 09:00~18:00 (KST, 공휴일 제외)
- 긴급(Sev1) 대응: 서명된 파일럿 계약/주문서에 기입된 Sev1 채널 기준

(상세: `03_SUPPORT_AND_ESCALATION.md`)

---

## 2) 심각도 및 응답 목표 (Design Partner, Best Effort)

| 심각도 | 정의(요약) | 1차 응답 목표 (Best Effort) |
|---|---|---:|
| Sev1 | Critical settlement/state/export control-plane failure affecting production use / 보안 사고 의심 | 4시간 |
| Sev2 | Major degraded control-plane functionality or blocked integration | 8시간 |
| Sev3 | Standard technical/support request | 1영업일 |
| Sev4 | General questions, roadmap, minor documentation issues | 2영업일 |

**주요 주의**:
- **Response target ≠ Resolution target**: 위의 목표는 "1차 응답" 목표이며, 해결 시점을 보장하지 않습니다.
- 모델 품질 / 프롬프트 정확성 / 외부 LLM 제공자 장애는 본 SLA 범위에서 제외됩니다.
- Sev1의 실제 목표치 및 24/7 적용 여부는 `10_ORDER_FORM_ONE_PAGER.md`(주문서)에서 확정합니다.

---

## 3) 가용성(Availability) 목표 (Design Partner 한정)

- 목표: 월 99.0% (Best Effort) — **본 목표는 서명된 Design Partner 계약에 포함된 경우에만 적용되며**, 공개 Sandbox Terms 상의 "No uptime SLA" 기준과 별개입니다.
- 측정: Decisionproof 측 모니터링 기준, 계획된 점검 시간 제외.

### 계획된 점검(Planned Maintenance)

- 점검 공지: 최소 7일 전(가능한 경우)
- 긴급 보안 패치: 사후 공지 가능

---

## 4) 제외(Exclusions)

다음은 SLA-lite 산정/보상 논의에서 제외됩니다.

- 고객 네트워크/환경 문제
- 고객의 오남용(AUP 위반) 또는 비정상 트래픽
- 외부 의존 서비스 장애(클라우드 리전 장애, LLM provider 장애 등)로 Decisionproof가 통제할 수 없는 경우
- 모델 출력 품질 / 프롬프트 정확성 / 고객이 제공한 입력에 기인한 실패

---

## 5) 보상(선택, Design Partner 파일럿 권장안)

- 기본값: 현금 환불 대신 **서비스 크레딧** 또는 **기간 연장**을 우선 검토
- 상세 절차: `11_DISPUTE_PLAYBOOK.md`
- 본 보상 항목은 Sandbox 고객에게는 적용되지 않음 (Sandbox refund는 Terms §7 참조)

---

## 6) Sandbox vs Design Partner 지원 분리 (MT0A-1)

| 항목 | Sandbox (paid private beta) | Design Partner (B2B 계약) |
|---|---|---|
| 지원 경로 | email (contact.html, terms.html) | 서명된 Order Form 의 Sev1 채널 |
| 응답 목표 | target first response within 1 business day (best effort) | Sev1 4h / Sev2 8h / Sev3 1영업일 / Sev4 2영업일 (best effort) |
| 24/7 on-call | 없음 | Order Form 에 따름 |
| 가용성 SLA | 없음 (No uptime SLA) | 월 99.0% best effort (계약 기반) |
| 모델 품질 지원 | 제외 | 제외 |

---

본 문서는 법률 자문이 아니며, 최종 SLA는 별도 서명 계약 문서로 확정됩니다.
