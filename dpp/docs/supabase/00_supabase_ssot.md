# Supabase Connection SSOT (Single Source of Truth)

**버전**: v1.0
**마지막 업데이트**: 2026-02-17

---

## 1. 정책 개요

**DPP (Decisionwise API Platform)의 Supabase 연결 방식은 다음과 같이 고정됩니다:**

1. **Pooler Transaction Mode** (port 6543) 사용
2. **NullPool** (SQLAlchemy poolclass) 사용
3. **sslmode=require** 강제
4. **직접 연결 금지** (port 5432 Session mode 금지)

이 정책은 **Production Guardrails (P0-1)**로 코드에서 강제됩니다.

---

## 2. Supabase 연결 모드 비교

### 2.1. Pooler Transaction Mode (Port 6543) ✅ **DPP 표준**

**특징**:
- Supabase가 제공하는 **PgBouncer Pooler** 사용
- 연결 당 트랜잭션 수명 (transaction-level pooling)
- 동시 연결 수 제한 없음 (Pooler가 관리)
- Serverless/Lambda 환경에 최적화

**연결 문자열 예시**:
```
postgres://postgres.abcdefgh:password@aws-0-us-east-1.pooler.supabase.com:6543/postgres?sslmode=require
```

**DPP 사용 이유**:
- FastAPI + Uvicorn 환경에서 **NullPool**과 조합 시 최적 성능
- Serverless 배포 시 연결 관리 부담 최소화
- Supabase 권장 모드 (공식 문서 기준)

### 2.2. Session Mode (Port 5432) ❌ **DPP 금지**

**특징**:
- Supabase Pooler 사용 (Session-level pooling)
- 장시간 세션 유지 (long-lived connections)
- Direct connection보다 안정적

**DPP 미사용 이유**:
- Transaction mode와 혼동 가능
- NullPool 조합 시 이점 없음
- 프로덕션 환경에서 혼란 방지 (단일 표준 유지)

### 2.3. Direct Connection (Port 5432, no pooler) ❌ **DPP 금지**

**특징**:
- Supabase PostgreSQL에 직접 연결
- Pooler 없이 raw connection 사용

**DPP 금지 이유**:
- 동시 연결 수 제한 (Supabase Free: 60개, Pro: 200개)
- 런타임 환경에서 연결 관리 부담 증가
- Pooler Transaction mode로 모든 요구사항 충족 가능

---

## 3. DPP SQLAlchemy 설정

### 3.1. Poolclass: NullPool (기본값)

**설정**:
```python
from sqlalchemy import create_engine, NullPool

engine = create_engine(
    database_url,
    poolclass=NullPool,
    pool_pre_ping=True,
    connect_args={"sslmode": "require"}
)
```

**NullPool 사용 이유**:
1. **Supabase Pooler Transaction Mode와 조합 최적**
   - Pooler가 이미 연결 풀링 담당
   - 클라이언트 측 풀링 중복 방지

2. **Serverless/Kubernetes 환경 적합**
   - 매 요청마다 새 연결 생성 → Pooler가 재사용
   - 유휴 연결 관리 부담 없음

3. **트랜잭션 격리 보장**
   - 요청 간 연결 재사용 없음 → 상태 누수 방지

### 3.2. QueuePool (선택적, 개발 환경만)

**설정**:
```bash
export DPP_DB_POOL=queuepool
export DPP_DB_POOL_SIZE=5
export DPP_DB_MAX_OVERFLOW=10
```

**사용 시나리오**:
- 로컬 개발 환경 (LocalStack, Docker PostgreSQL)
- 짧은 요청 간격에서 연결 재사용으로 성능 향상

**프로덕션 미사용 이유**:
- Supabase Pooler와 중복 풀링 → 효율 저하 가능
- NullPool로 충분한 성능 달성

---

## 4. Production Guardrails (P0-1)

### 4.1. 자동 검증 (engine.py)

**코드 위치**: `dpp/apps/api/dpp_api/db/engine.py`

**검증 항목**:
1. ✅ Port 6543 (Pooler Transaction mode)
2. ✅ Hostname에 "pooler" 포함
3. ✅ sslmode=require 포함
4. ✅ SUPABASE_SERVICE_ROLE_KEY 환경변수 부재

**에러 예시**:
```
RuntimeError: PRODUCTION GUARDRAIL: Supabase port must be 6543 (Pooler Transaction mode), got 5432.
Fix: Use Pooler Transaction mode connection string from Supabase Dashboard.
```

### 4.2. 배포 전 검증

**Preflight 스크립트**:
```bash
python scripts/supabase_preflight.py
# 출력: PASS: Supabase production preflight validation successful
```

**환경변수 체크**:
```bash
# 필수
DP_ENV=prod
DATABASE_URL=postgres://...@host.pooler.supabase.com:6543/postgres?sslmode=require

# ACK 변수 (P0-2, P0-4)
DPP_ACK_SUPABASE_NETWORK_RESTRICTIONS=1
DPP_ACK_SUPABASE_BACKUP_POLICY=1
```

---

## 5. 연결 문자열 획득 방법

### 5.1. Supabase Dashboard

1. [https://supabase.com/dashboard](https://supabase.com/dashboard) 로그인
2. 프로젝트 선택
3. **Settings** → **Database** 메뉴
4. **Connection string** 섹션에서 선택:
   - **Transaction Mode** (Port 6543) ✅ **DPP 표준**
   - ~~Session Mode (Port 5432)~~ ❌ 사용 금지
   - ~~Direct Connection~~ ❌ 사용 금지

### 5.2. 연결 문자열 포맷

**올바른 예시** ✅:
```
postgres://postgres.abcdefgh:your-password@aws-0-us-east-1.pooler.supabase.com:6543/postgres?sslmode=require
```

**잘못된 예시** ❌:
```
# Port 5432 (Session mode 또는 Direct)
postgres://postgres.abcdefgh:password@db.supabase.co:5432/postgres

# Pooler 없음
postgres://postgres.abcdefgh:password@db.supabase.co:6543/postgres

# sslmode 누락
postgres://postgres.abcdefgh:password@aws-0-us-east-1.pooler.supabase.com:6543/postgres
```

---

## 6. 비상 Override (긴급 상황만)

**환경변수**:
```bash
# Port 6543 외 허용 (매우 비권장)
DPP_SUPABASE_ALLOW_NON_6543=1

# Pooler 없는 연결 허용 (매우 비권장)
DPP_SUPABASE_ALLOW_DIRECT=1

# ACK 체크 우회 (절대 프로덕션 사용 금지)
DPP_ACK_BYPASS=1
```

**사용 시나리오**:
- Supabase Pooler 장애 발생 시 긴급 복구
- 테스트 목적 (CI/CD 환경)

**주의**:
- ⚠️ **프로덕션에서 절대 사용 금지**
- ⚠️ 로그에 WARNING 출력됨
- ⚠️ 사용 후 즉시 원복 필요

---

## 7. 참고 자료

- Supabase 공식 문서: [Database Connections](https://supabase.com/docs/guides/database/connecting-to-postgres)
- SQLAlchemy Pooling: [Engine Configuration](https://docs.sqlalchemy.org/en/20/core/pooling.html)
- DPP Engine Code: `dpp/apps/api/dpp_api/db/engine.py`
- Preflight Validator: `dpp/scripts/supabase_preflight.py`

---

**이 문서는 DPP Supabase 연결 정책의 SSOT입니다.**
**변경 시 반드시 DevOps/Backend 팀 리뷰 필요.**
