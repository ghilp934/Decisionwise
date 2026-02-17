# Supabase Database Backup and Restore Runbook

**목적**: Supabase 프로덕션 데이터베이스 백업 및 복원 절차

**담당자**: DevOps/운영팀

**백업 빈도**: 일일 1회 (크론잡 자동화 권장)

---

## P0-4: 백업 정책 및 절차

### 1. 백업 생성 (pg_dump)

**명령어**:
```bash
# DATABASE_URL 환경변수 사용
./ops/scripts/db_backup_pgdump.sh

# 또는 명시적 URL 전달
./ops/scripts/db_backup_pgdump.sh --url "postgres://user:pass@aws-0-region.pooler.supabase.com:6543/postgres?sslmode=require"
```

**출력**:
```
backups/dpp_20260217_120000.sql.gz
```

**자동화 (cron 예시)**:
```cron
# 매일 새벽 2시 백업
0 2 * * * cd /path/to/dpp && ./ops/scripts/db_backup_pgdump.sh >> logs/backup.log 2>&1
```

**주의사항**:
- ✅ Supabase Pooler Transaction mode (port 6543) 사용 확인
- ✅ 백업 파일은 안전한 위치에 보관 (S3, GCS 등)
- ✅ 최소 7일간 백업 보관 권장

### 2. 백업 복원 (pg_restore)

**명령어**:
```bash
./ops/scripts/db_restore_verify.sh \
  --file backups/dpp_20260217_120000.sql.gz \
  --target-url "postgres://user:pass@test-db.pooler.supabase.com:6543/postgres?sslmode=require"
```

**동작**:
1. 백업 파일 압축 해제 (gunzip)
2. psql로 데이터 복원
3. 주요 테이블 row count 검증 출력

**출력 예시**:
```
schemaname | tablename           | row_count
-----------+---------------------+-----------
public     | api_keys            |        12
public     | plans               |         3
public     | runs                |      1523
public     | tenant_plans        |        15
public     | tenant_usage_daily  |       245
public     | tenants             |        10
```

**주의사항**:
- ⚠️ **프로덕션 복원은 매우 신중하게** (데이터 덮어쓰기 위험)
- ⚠️ 복원 전 반드시 현재 상태 백업 생성
- ⚠️ 테스트 환경에서 먼저 복원 테스트 권장

### 3. 복원 검증 절차

**복원 후 체크리스트**:
- [ ] 주요 테이블 row count 확인 (위 출력 참고)
- [ ] 최신 데이터 존재 확인 (tenants, runs 테이블)
- [ ] API 헬스체크 통과 (`GET /health`)
- [ ] 샘플 API 요청 정상 동작 확인

**추가 검증 (선택 사항)**:
```bash
# 특정 tenant 데이터 확인
psql "$DATABASE_URL" -c "SELECT id, email FROM tenants LIMIT 5;"

# 최근 run 데이터 확인
psql "$DATABASE_URL" -c "SELECT id, status, created_at FROM runs ORDER BY created_at DESC LIMIT 5;"
```

### 4. Supabase Point-in-Time Recovery (PITR)

**Supabase 기본 백업**:
- Supabase는 자동으로 매일 백업 생성 (무료 플랜: 7일 보관)
- 유료 플랜: Point-in-Time Recovery (PITR) 지원

**PITR 사용 방법**:
1. Supabase Dashboard → Settings → Database → **Backups**
2. 복원 시점 선택 (최대 7일 전)
3. **Restore** 클릭 → 새 프로젝트로 복원됨

**주의**:
- ⚠️ PITR 복원은 새 프로젝트 생성 (기존 DB 덮어쓰기 아님)
- ⚠️ 복원 후 DATABASE_URL 변경 필요

---

## ACK 변수 설정

**백업/복원 절차 검증 완료 후**:
```bash
# Kubernetes Secret 또는 환경변수에 추가
DPP_ACK_SUPABASE_BACKUP_POLICY=1
```

**목적**: 엔진 시작 시 production guardrail에서 백업 정책 검증 완료 확인

**에러 발생 시**:
```
RuntimeError: DPP_ACK_SUPABASE_BACKUP_POLICY=1 required.
This confirms backup/restore procedures tested and scheduled.
```

→ 이 runbook 체크리스트 완료 후 ACK 변수 설정

---

## 체크리스트

배포 전 아래 항목 모두 확인:

- [ ] `db_backup_pgdump.sh` 스크립트 테스트 (백업 생성 성공)
- [ ] `db_restore_verify.sh` 스크립트 테스트 (테스트 환경에서 복원 성공)
- [ ] 백업 파일 보관 위치 확정 (S3/GCS 버킷 등)
- [ ] 백업 자동화 설정 (cron 또는 Kubernetes CronJob)
- [ ] 복원 절차 문서화 (담당자 공유)
- [ ] `DPP_ACK_SUPABASE_BACKUP_POLICY=1` 환경변수 설정
- [ ] `python scripts/supabase_preflight.py` 실행 → PASS 확인

---

## 참고 자료

- Supabase 공식 문서: [Database Backups](https://supabase.com/docs/guides/database/backups)
- DPP Backup Scripts: `dpp/ops/scripts/db_backup_pgdump.sh`, `db_restore_verify.sh`
- Supabase SSOT 문서: `dpp/docs/supabase/00_supabase_ssot.md`

---

**마지막 업데이트**: 2026-02-17
**리뷰 주기**: 분기 1회 (백업 정책 변경 시 즉시 업데이트)
