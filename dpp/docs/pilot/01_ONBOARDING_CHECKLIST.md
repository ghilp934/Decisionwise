# Onboarding Checklist

**Decisionproof API Platform - Paid Pilot Onboarding**

---

## 온보딩 목표

파일럿 시작 후 **1영업일 내** 첫 API 호출 성공을 목표로 합니다.

---

## 체크리스트

### Phase 1: 계정 및 토큰 발급

- [ ] **1.1 계정 생성 확인**
  - 담당자: Decisionproof 운영팀
  - 수령 정보: 가입 승인 이메일 (계정 ID, Workspace ID)
  - 예상 시간: 계약 체결 후 1영업일

- [ ] **1.2 Staging API Key 발급**
  - 방법: 담당자 이메일 요청 → 암호화된 방식으로 전달
  - 형식: `sk_staging_...` (Bearer 토큰)
  - 보안: 즉시 안전한 곳에 저장 (환경변수/Vault)
  - ⚠️ **절대 코드/로그에 노출 금지**

- [ ] **1.3 토큰 유효성 확인**
  ```bash
  curl -H "Authorization: Bearer sk_staging_..." \
    https://staging-api.decisionproof.ai/v1/runs
  ```
  - 예상 응답: `200 OK` (빈 배열) 또는 `401 Unauthorized` (토큰 오류)

### Phase 2: 네트워크 및 방화벽 설정

- [ ] **2.1 Staging 엔드포인트 접근 확인**
  ```bash
  curl -v https://staging-api.decisionproof.ai/health
  ```
  - 예상 응답: `200 OK`, `{"status": "healthy", ...}`

- [ ] **2.2 방화벽 허용 (필요 시)**
  - 대상: `staging-api.decisionproof.ai` (TLS 443)
  - IP 화이트리스트: 불필요 (공개 엔드포인트)
  - 프록시 설정: 자사 환경에 맞게 설정

- [ ] **2.3 DNS 해석 확인**
  ```bash
  nslookup staging-api.decisionproof.ai
  ```
  - 예상: A 레코드 반환 (IP 주소)

### Phase 3: 첫 API 호출 (Health Check)

- [ ] **3.1 /health 엔드포인트 호출**
  ```bash
  curl https://staging-api.decisionproof.ai/health
  ```
  - 예상 응답:
    ```json
    {
      "status": "healthy",
      "version": "0.4.2.2",
      "services": {"api": "up", "database": "up", "redis": "up", "s3": "up", "sqs": "up"}
    }
    ```

- [ ] **3.2 /readyz 엔드포인트 호출**
  ```bash
  curl https://staging-api.decisionproof.ai/readyz
  ```
  - 예상 응답: `200 OK` (모든 서비스 "up") 또는 `503 Service Unavailable` (일부 서비스 "down")

- [ ] **3.3 OpenAPI 스펙 확인**
  ```bash
  curl https://staging-api.decisionproof.ai/.well-known/openapi.json | jq '.info'
  ```
  - 예상 응답: `{"title": "Decisionproof API", "version": "0.4.2.2", ...}`

### Phase 4: 인증된 API 호출 (Runs)

- [ ] **4.1 Bearer 토큰으로 /v1/runs 호출**
  ```bash
  export DPP_STAGING_TOKEN="sk_staging_..."
  curl -H "Authorization: Bearer $DPP_STAGING_TOKEN" \
    https://staging-api.decisionproof.ai/v1/runs
  ```
  - 예상 응답: `200 OK`, `{"runs": []}` (빈 배열 또는 기존 runs)

- [ ] **4.2 첫 Decision Run 생성 (상세: 02_QUICKSTART_FOR_PILOT.md)**

### Phase 5: 모니터링 및 로깅 설정

- [ ] **5.1 Rate Limit 헤더 확인**
  - 응답 헤더: `RateLimit-Policy`, `RateLimit`
  - 파일럿 제한: 60 RPM (STARTER 플랜)

- [ ] **5.2 자사 시스템 로깅 설정**
  - API 호출 시 `request_id` 헤더 기록 (디버깅용)
  - 오류 발생 시 응답 본문 전체 저장 (RFC 9457 Problem Details)

- [ ] **5.3 테스트 시나리오 10개 정의**
  - 예: "헬스 체크", "토큰 인증", "Run 생성", "Run 조회", ...
  - 성공 기준: 10개 중 10개 성공

---

## 성공 기준

### 온보딩 완료 조건

- ✅ Phase 1~4 모든 항목 체크
- ✅ `/health` 및 `/v1/runs` 호출 성공
- ✅ 토큰 유효성 확인 완료
- ✅ 자사 시스템에서 API 호출 가능 (프록시/방화벽 통과)

### 예상 소요 시간

- 계정 발급: 1영업일 (Decisionproof 운영팀)
- 네트워크 설정: 0.5일 (고객 IT 팀)
- 첫 호출 성공: 0.5일 (고객 개발 팀)
- **총**: 2영업일

---

## 문제 해결

### 문제 1: 토큰 발급 지연

**증상:** 계약 체결 후 2영업일이 지나도 토큰 미수령

**조치:**
1. pilot-support@decisionproof.ai로 문의
2. 계약서 번호 및 담당자 정보 제공
3. 긴급 시 Slack #dpp-pilot-support 멘션

### 문제 2: 401 Unauthorized

**증상:** Bearer 토큰 사용했으나 401 응답

**원인:**
- 토큰 오타 또는 공백 포함
- 토큰 만료 (파일럿 종료 시 자동 만료)
- `Authorization` 헤더 형식 오류

**조치:**
```bash
# 올바른 형식
curl -H "Authorization: Bearer sk_staging_..." https://...

# 잘못된 형식 (X)
curl -H "Authorization: sk_staging_..." https://...  # "Bearer" 누락
curl -H "Token: Bearer sk_staging_..." https://...  # "Authorization" 아님
```

### 문제 3: 503 Service Unavailable (/readyz)

**증상:** `/health`는 200이지만 `/readyz`는 503

**원인:** 일부 의존 서비스 (DB/Redis/S3/SQS) 다운

**조치:**
1. 응답 본문 확인: `{"services": {"database": "down: ..."}}` → 어떤 서비스가 다운인지 확인
2. 5분 대기 후 재시도 (일시적 문제 가능성)
3. 지속 시 pilot-support로 즉시 보고

---

## 다음 단계

온보딩 완료 후:
1. `02_QUICKSTART_FOR_PILOT.md`로 실제 Decision Run 호출
2. `03_SUPPORT_AND_ESCALATION.md`로 지원 채널 숙지
3. 테스트 시나리오 10개 실행 및 결과 기록
