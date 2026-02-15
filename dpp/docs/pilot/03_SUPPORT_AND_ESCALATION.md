# Support and Escalation

**Decisionproof API - 지원 및 장애 대응**

---

## 지원 채널

### 이메일 지원

**주소:** ghilplip934@gmail.com

**사용 시기:**
- 일반 문의 (S2/S3)
- 기술 질문
- 계정/토큰 관련

**응답 목표:**
- S2 (일반 문의): 4시간 (영업시간 내)
- S3 (기능 요청): 1영업일

### 운영 시간

**정규 지원:**
- 월요일~금요일 09:00~18:00 (KST)
- 공휴일 제외

**긴급 지원:**
- 파일럿 기간 중 24/7 긴급 지원 **제외**
- 영업시간 외 발생 이슈는 다음 영업일 처리

---

## 심각도 정의

### S0: 서비스 중단

**정의:**
- Staging API 전체 접근 불가 (5xx 오류 또는 timeout)
- 모든 엔드포인트 응답 없음

**예시:**
- `/health` 호출 시 연결 실패
- DNS 해석 실패
- 인증서 오류

**응답 목표:** 1시간 (최선 노력)

**에스컬레이션:** 즉시 Slack + 이메일 동시 발송

### S1: 주요 기능 오류

**정의:**
- 핵심 API 엔드포인트 오류 (/v1/runs 등)
- 인증 실패 (토큰 정상이나 401 반환)
- 잘못된 과금 (실제 사용량과 청구 불일치)

**예시:**
- `/v1/runs` POST 시 500 Internal Server Error
- 정상 토큰으로 401 Unauthorized
- 크레딧 차감 오류

**응답 목표:** 2시간

**에스컬레이션:** Slack 우선, 2시간 무응답 시 이메일 재발송

### S2: 일반 문의

**정의:**
- 비핵심 기능 오류
- 문서/가이드 관련 질문
- 성능 문의 (응답 지연 등)

**예시:**
- Rate Limit 헤더 해석 방법
- OpenAPI 스펙 다운로드 실패
- API 응답 시간 1초 초과

**응답 목표:** 4시간 (영업시간 내)

**채널:** 이메일 또는 Slack

### S3: 기능 요청

**정의:**
- 신규 기능 제안
- 문서 개선 요청
- 정책 변경 건의

**예시:**
- Webhook 지원 요청
- 추가 엔드포인트 제안
- Rate Limit 증량 요청

**응답 목표:** 1영업일

**채널:** 이메일

---

## 증빙 제출 가이드

### 문제 보고 시 필수 정보

지원 요청 시 아래 정보를 포함하면 빠른 해결이 가능합니다:

```
1. 심각도: S0/S1/S2/S3
2. 발생 시각: YYYY-MM-DD HH:MM:SS (KST)
3. 엔드포인트: https://staging-api.decisionproof.ai/...
4. Request ID: req_xyz... (응답 헤더 또는 본문에서 확인)
5. 재현 방법:
   curl -X POST \
     -H "Authorization: Bearer sk_staging_..." \
     -d '{"..."}' \
     https://...
6. 예상 동작: 200 OK 응답 예상
7. 실제 동작: 500 Internal Server Error 수신
8. 응답 본문: {"type": "...", "detail": "..."}
```

### Evidence 폴더 활용

자사 시스템에서 Evidence를 수집하여 첨부하면 더욱 빠릅니다:

```bash
# 예시: 오류 발생 시 로그 수집
mkdir -p evidence/issue_$(date +%Y%m%d_%H%M%S)
cd evidence/issue_$(date +%Y%m%d_%H%M%S)

# Request/Response 저장
curl -v -H "Authorization: Bearer $TOKEN" \
  https://staging-api.decisionproof.ai/v1/runs \
  > response.log 2> request.log

# 재현 커맨드 저장
echo "curl -H 'Authorization: Bearer $TOKEN' https://..." > reproduce.sh

# 압축 후 첨부
cd .. && zip -r issue_$(date +%Y%m%d_%H%M%S).zip issue_$(date +%Y%m%d_%H%M%S)
```

---

## 에스컬레이션 경로

### Level 1: 파일럿 지원팀

- **채널:** ghilplip934@gmail.com
- **대상:** S1/S2/S3 모든 이슈
- **SLA:** 상기 응답 목표

### Level 2: 엔지니어링 팀

- **조건:** S0 또는 S1이 4시간 이상 미해결
- **방법:** 파일럿 지원팀이 자동 에스컬레이션
- **알림:** Slack에서 진행 상황 공유

### Level 3: 긴급 담당자

- **조건:** S0이 2시간 이상 미해결
- **연락처:** [09_CHANGELOG_AND_CONTACTS.md 참조]
- **방법:** 전화 또는 SMS

---

## SLA 및 제한사항

### 파일럿 기간 중 SLA

⚠️ **파일럿 기간 중에는 정식 SLA가 적용되지 않습니다.**

- Uptime 보장: 없음 (최선 노력)
- 응답 시간: 목표치이며 보장 아님
- 보상: SLA 위반 시 보상 없음

### Production 전환 시

정식 계약 전환 후에는 별도 SLA 적용 (협의 필요):
- Uptime: 99.9% (월간)
- S0 응답: 30분
- S1 응답: 1시간
- 보상: 크레딧 환급 등

---

## 다음 단계

1. 지원 채널 (이메일) 접속 확인
2. 테스트 문의 1건 발송하여 응답 시간 체험
3. 문제 발생 시 위 가이드대로 증빙 수집 및 제출
