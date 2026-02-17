# Supabase Secrets and API Keys Policy

**버전**: v1.0
**마지막 업데이트**: 2026-02-17

---

## 1. 정책 요약

**DPP (Decisionwise API Platform)는 Supabase API Keys를 사용하지 않습니다.**

### 금지 항목:
- ❌ `SUPABASE_SERVICE_ROLE_KEY`
- ❌ `SUPABASE_ANON_KEY`
- ❌ Supabase Client Libraries (`@supabase/supabase-js`, `supabase-py`)
- ❌ Supabase RESTful API 호출

### 허용 항목:
- ✅ PostgreSQL 직접 연결 (`DATABASE_URL`)
- ✅ SQLAlchemy ORM
- ✅ psycopg2/asyncpg drivers

---

## 2. 왜 Supabase API Keys를 사용하지 않는가?

### 2.1. 서버 사이드 아키텍처

**DPP는 서버 사이드 API 플랫폼입니다:**
- 클라이언트 브라우저와 직접 통신하지 않음
- Supabase Auth, Storage, Realtime 기능 미사용
- PostgreSQL 데이터베이스만 사용

**Supabase API Keys 필요 시나리오 (DPP 해당 없음)**:
- ❌ 브라우저/모바일 앱에서 Supabase 직접 호출
- ❌ Supabase Auth (JWT 인증) 사용
- ❌ Supabase Storage (파일 업로드) 사용
- ❌ Supabase Realtime (WebSocket) 사용

### 2.2. 보안 위험 최소화

**API Keys 노출 시 공격 벡터**:
1. **SERVICE_ROLE_KEY 유출** → RLS (Row Level Security) 우회 가능
2. **불필요한 권한** → 공격 표면 증가
3. **키 관리 부담** → 로테이션, 저장소 보안

**DPP 접근 방식**:
- PostgreSQL 직접 연결 (DATABASE_URL) → 최소 권한 원칙
- RLS는 방어 계층일 뿐, 애플리케이션 로직에서 권한 관리
- API Keys 없음 → 유출 걱정 불필요

### 2.3. 아키텍처 단순성

**Supabase API Keys 사용 시**:
```
Client → DPP API → Supabase Client (supabase-py) → Supabase RESTful API → PostgreSQL
```

**DPP 방식 (직접 연결)**:
```
Client → DPP API → PostgreSQL (via SQLAlchemy)
```

**이점**:
- 레이어 감소 → 디버깅 용이
- Dependency 감소 → 보안 취약점 최소화
- 성능 향상 → REST API overhead 없음

---

## 3. Supabase API Keys 검출 및 차단

### 3.1. Production Guardrails (P0-3)

**코드 위치**: `dpp/apps/api/dpp_api/db/engine.py`

**엔진 시작 시 자동 검증**:
```python
if os.getenv("SUPABASE_SERVICE_ROLE_KEY") or os.getenv("SUPABASE_ANON_KEY"):
    raise RuntimeError(
        "PRODUCTION GUARDRAIL: SUPABASE_SERVICE_ROLE_KEY or SUPABASE_ANON_KEY detected. "
        "This project uses direct Postgres connections only (server-side). "
        "Fix: Remove SUPABASE_SERVICE_ROLE_KEY and SUPABASE_ANON_KEY from deployment config."
    )
```

**에러 발생 시**:
```
RuntimeError: PRODUCTION GUARDRAIL: SUPABASE_SERVICE_ROLE_KEY or SUPABASE_ANON_KEY detected.
```

→ 배포 설정에서 해당 환경변수 제거 필요

### 3.2. Runtime Hygiene Check (CI/CD)

**스크립트**: `dpp/scripts/runtime_secret_hygiene_check.py`

**사용 방법**:
```bash
# 배포 전 실행
python scripts/runtime_secret_hygiene_check.py

# CI/CD에서 실행 (경고만)
python scripts/runtime_secret_hygiene_check.py --relaxed
```

**검출 패턴**:
- `SUPABASE_SERVICE_ROLE_KEY=...`
- `SUPABASE_ANON_KEY=...`
- `https://*.supabase.co` (URL)
- `service_role` (토큰 값)

**스캔 경로**:
- `dpp/k8s/**/*.yaml`
- `dpp/.env*`
- `dpp/apps/**/.env*`

### 3.3. Preflight Validation

**스크립트**: `dpp/scripts/supabase_preflight.py`

**사용 방법**:
```bash
# 프로덕션 배포 직전 실행
export DP_ENV=prod
export DATABASE_URL="postgres://...@host.pooler.supabase.com:6543/postgres?sslmode=require"
python scripts/supabase_preflight.py
```

**검증 항목**:
- ✅ DATABASE_URL 형식 (port 6543, pooler, sslmode)
- ✅ SUPABASE_SERVICE_ROLE_KEY 부재
- ✅ SUPABASE_ANON_KEY 부재

---

## 4. Supabase Dashboard에서 API Keys 관리

### 4.1. API Keys 조회 (정보 목적만)

**경로**: Settings → API → **Project API keys**

**표시되는 키**:
- `anon` (public) key
- `service_role` (secret) key

**주의**:
- ⚠️ **DPP 런타임 환경에 절대 설정 금지**
- ⚠️ 개발자 로컬 환경에서도 불필요
- ⚠️ 복사/저장 자제 (유출 위험)

### 4.2. API Keys 사용 시나리오 (DPP 외부)

**허용 상황**:
- 프론트엔드 앱 (브라우저/모바일)에서 Supabase 직접 호출
- Supabase Auth/Storage/Realtime 기능 사용
- Supabase Edge Functions 개발

**DPP와 독립적**:
- DPP API는 Supabase API Keys 불필요
- 별도 프론트엔드 프로젝트에서만 사용

---

## 5. 대안: PostgreSQL 직접 연결

### 5.1. DATABASE_URL 설정

**형식**:
```
postgres://[user]:[password]@[host]:[port]/[database]?sslmode=require
```

**예시**:
```bash
# 프로덕션 (Pooler Transaction Mode)
DATABASE_URL="postgres://postgres.abcdefgh:your-password@aws-0-us-east-1.pooler.supabase.com:6543/postgres?sslmode=require"

# 로컬 개발 (Docker PostgreSQL)
DATABASE_URL="postgres://postgres:postgres@localhost:5432/dpp_dev"
```

### 5.2. SQLAlchemy ORM 사용

**코드 예시**:
```python
from dpp_api.db.engine import build_engine, build_sessionmaker

# Engine 생성 (NullPool, Supabase Pooler Transaction Mode)
engine = build_engine()
SessionLocal = build_sessionmaker(engine)

# Session 사용
with SessionLocal() as session:
    tenants = session.query(Tenant).all()
```

**이점**:
- ✅ Supabase API Keys 불필요
- ✅ Python ORM 표준 패턴
- ✅ 타입 안전성 (mypy, pyright)

### 5.3. Row Level Security (RLS) 동작

**Supabase RLS는 여전히 활성화됨**:
- RLS는 PostgreSQL 네이티브 기능
- DATABASE_URL로 연결해도 RLS 정책 적용

**DPP에서 RLS 처리**:
- RLS는 **방어 계층**으로만 사용 (defense-in-depth)
- 애플리케이션 로직에서 tenant_id 필터링 명시
- RLS 정책: 기본 DENY (별도 ALLOW 정책 없음)

**코드 예시**:
```python
# 애플리케이션에서 tenant_id 필터링 (RLS와 독립적)
runs = session.query(Run).filter(Run.tenant_id == tenant_id).all()
```

---

## 6. 긴급 Override (매우 비권장)

**환경변수**:
```bash
# API Keys 허용 (매우 비권장)
DPP_ALLOW_SUPABASE_API_KEYS=1
```

**사용 시나리오**:
- 레거시 마이그레이션 과정
- 테스트 환경 (Supabase Client Library 검증)

**주의**:
- ⚠️ 프로덕션에서 절대 사용 금지
- ⚠️ 사용 시 반드시 ACK 변수 설정 필요
- ⚠️ 로그에 WARNING 출력됨

---

## 7. 체크리스트

배포 전 아래 항목 확인:

- [ ] Kubernetes Secrets에 `SUPABASE_SERVICE_ROLE_KEY` 없음
- [ ] Kubernetes Secrets에 `SUPABASE_ANON_KEY` 없음
- [ ] `.env` 파일에 위 키들 없음
- [ ] `python scripts/runtime_secret_hygiene_check.py` 실행 → PASS
- [ ] `python scripts/supabase_preflight.py` 실행 → PASS
- [ ] 프로덕션 환경변수에 `DATABASE_URL`만 존재

---

## 8. 참고 자료

- Supabase API Keys 문서: [API Settings](https://supabase.com/docs/guides/api)
- PostgreSQL Row Level Security: [RLS Documentation](https://www.postgresql.org/docs/current/ddl-rowsecurity.html)
- DPP Engine Code: `dpp/apps/api/dpp_api/db/engine.py`
- Hygiene Check Script: `dpp/scripts/runtime_secret_hygiene_check.py`
- Supabase SSOT: `dpp/docs/supabase/00_supabase_ssot.md`

---

**이 문서는 DPP Supabase Secrets 정책의 SSOT입니다.**
**변경 시 반드시 DevOps/Security 팀 리뷰 필요.**
