# Changelog and Contacts

**Decisionproof API - 변경 로그 및 연락처**

---

## 변경 공지 규칙

### 변경 유형

**Major (중대 변경):**
- API 스펙 변경 (Breaking Change)
- 요금제 변경
- 서비스 중단 계획

**공지 시기:** 최소 30일 전 이메일 공지

**Minor (일반 변경):**
- 신규 기능 추가
- 성능 개선
- 버그 수정

**공지 시기:** 7일 전 이메일 + Slack 공지

**Patch (긴급 수정):**
- 보안 패치
- 긴급 버그 수정

**공지 시기:** 사후 공지 (즉시 적용)

---

## 변경 로그

### 2026-02-15 (v0.4.2.2)

**변경:**
- Paid Pilot Kickoff Packet 발행
- STARTER 플랜 출시 (₩29,000/월, 1,000 DC)

**영향:**
- 신규 파일럿 고객 대상
- 기존 고객 영향 없음

### 2026-02-13 (v0.4.2.0)

**변경:**
- Kubernetes 배포 지원 추가
- Staging 환경 구축 완료

**영향:**
- Staging API 접근 가능

### 2026-02-01 (v0.4.0.0)

**변경:**
- RFC 9457 Problem Details 적용
- IETF RateLimit 헤더 추가

**영향:**
- 오류 응답 형식 변경 (application/problem+json)
- 하위 호환성 유지

---

## 담당자 및 연락처

### 파일럿 지원팀

**이름:** [파일럿 담당자명 - 별도 제공]
**이메일:** pilot-support@decisionproof.ai
**Slack:** #dpp-pilot-support
**운영 시간:** 월~금 09:00~18:00 (KST)

### 긴급 연락처

**조건:** S0 (서비스 중단) 2시간 이상 지속

**연락처:** [긴급 담당자 전화번호 - 별도 제공]
**사용 시간:** 영업시간 내 (월~금 09:00~18:00 KST)

⚠️ **파일럿 기간 중 24/7 긴급 지원 미제공**

### 계약 담당

**이메일:** contracts@decisionproof.ai
**용도:** 계약 변경, 연장, 종료, Production 전환

### 기술 문의

**이메일:** tech-support@decisionproof.ai
**Slack:** #dpp-tech-support
**용도:** API 기술 질문, 통합 가이드, 베스트 프랙티스

---

## 피드백 및 제안

### 기능 요청

**채널:** pilot-support@decisionproof.ai (제목: [Feature Request] ...)

**형식:**
```
제목: [Feature Request] Webhook 지원 요청
내용:
- 현재 문제: SQS 폴링 필요
- 제안 기능: Webhook으로 결과 수신
- 사용 사례: ...
- 우선순위: High/Medium/Low
```

### 문서 개선

**채널:** pilot-support@decisionproof.ai (제목: [Docs] ...)

**예시:**
- 오타/오류 신고
- 설명 추가 요청
- 예시 코드 제안

---

## 문서 버전 관리

### 현재 버전

**Kickoff Packet Version:** 2026-02-15
**API Version:** v0.4.2.2
**문서 저장소:** (내부 전용)

### 업데이트 이력

| 날짜 | 버전 | 변경 내용 |
|------|------|----------|
| 2026-02-15 | v1.0 | 초기 발행 |
| (향후 업데이트 시 추가) | | |

---

## 다음 단계

1. 주요 담당자 연락처 저장
2. Slack #dpp-pilot-support 가입
3. 변경 공지 이메일 수신 확인
4. 피드백/제안 사항 정리 및 제출 (필요 시)
