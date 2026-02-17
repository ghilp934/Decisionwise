# S3 Result Retention Cleanup Runbook (P0-6)

**목적**: 만료된 S3 result objects 자동 삭제 정책 및 운영 가이드

**담당자**: DevOps/운영팀

**자동화**: Reaper 서비스 Retention Loop (기본 활성화)

---

## 1. Retention Policy 개요

### 1.1. 정책

**기본 보관 기간**: 30일 (완료 후 경과 시간 기준)

**대상**:
- `status='COMPLETED'` 상태의 runs
- `completed_at < NOW - 30 days`
- `result_s3_key IS NOT NULL` (S3 result 존재)
- `result_cleared_at IS NULL` (아직 삭제되지 않음)

**동작**:
1. S3 result object 삭제 (`s3://bucket/key`)
2. DB `runs` 테이블에 `result_cleared_at` 타임스탬프 기록
3. DB `runs` row는 **삭제하지 않음** (감사 추적 보존)

### 1.2. 환경변수 설정

```bash
# Retention cleanup 활성화 (기본값: true)
DPP_RETENTION_ENABLED=true

# 보관 기간 (일 단위, 기본값: 30)
DPP_RETENTION_DAYS=30

# Retention Loop 실행 간격 (초 단위, 기본값: 86400 = 24시간)
DPP_RETENTION_LOOP_INTERVAL_SECONDS=86400
```

**커스터마이징 예시**:
```bash
# 90일 보관 정책
DPP_RETENTION_DAYS=90

# 매 12시간마다 실행
DPP_RETENTION_LOOP_INTERVAL_SECONDS=43200

# Retention cleanup 비활성화
DPP_RETENTION_ENABLED=false
```

---

## 2. Retention Loop 운영

### 2.1. 모니터링

**로그 확인** (Reaper 서비스):
```bash
# Kubernetes
kubectl logs -f deployment/dpp-reaper -n dpp-production | grep Retention

# Docker
docker logs -f dpp-reaper | grep Retention
```

**정상 동작 로그 예시**:
```
2026-02-17T12:00:00.000Z INFO Starting Retention Loop thread...
2026-02-17T12:00:05.000Z INFO Found 25 expired runs for retention cleanup
2026-02-17T12:00:10.000Z INFO Retention cleanup completed: 25 S3 objects deleted, 25 runs marked as cleared
```

**경고 로그 예시**:
```
2026-02-17T12:00:05.000Z WARNING Run abc123 missing S3 info, skipping
2026-02-17T12:00:06.000Z ERROR Failed to delete S3 object for run def456: ClientError(...)
```

### 2.2. 메트릭 (선택 사항)

**Prometheus/Grafana**:
- `retention_cleanup_runs_scanned_total`: 스캔된 runs 수
- `retention_cleanup_s3_objects_deleted_total`: 삭제된 S3 objects 수
- `retention_cleanup_errors_total`: 삭제 실패 수

(구현 시 `retention_loop.py`에 메트릭 추가 필요)

### 2.3. 비활성화 방법

**일시적 비활성화** (재배포 필요):
```bash
# Kubernetes ConfigMap/Secret 수정
kubectl edit configmap dpp-config -n dpp-production

# DPP_RETENTION_ENABLED=false 설정 후 재배포
kubectl rollout restart deployment/dpp-reaper -n dpp-production
```

**영구적 비활성화**:
```yaml
# k8s/configmap.yaml 또는 Helm values.yaml
env:
  - name: DPP_RETENTION_ENABLED
    value: "false"
```

---

## 3. 수동 Retention Cleanup

### 3.1. 수동 실행 (긴급 상황)

**Python 스크립트 실행**:
```python
from dpp_api.db.engine import build_engine, build_sessionmaker
from dpp_api.storage.s3_client import get_s3_client
from dpp_reaper.loops.retention_loop import run_retention_cleanup

# Database 연결
engine = build_engine()
SessionLocal = build_sessionmaker(engine)

# S3 client
s3_client = get_s3_client()

# 수동 실행
with SessionLocal() as session:
    deleted_count = run_retention_cleanup(
        session=session,
        s3_client=s3_client,
        cutoff_days=30,  # 30일 이전 데이터 삭제
        batch_size=100,  # 한 번에 100개까지 처리
    )
    print(f"Deleted {deleted_count} S3 objects")
```

### 3.2. 특정 tenant 데이터만 삭제

**SQL 쿼리로 대상 확인**:
```sql
-- 삭제 대상 runs 조회
SELECT run_id, tenant_id, completed_at, result_s3_key
FROM runs
WHERE status = 'COMPLETED'
  AND tenant_id = 'tenant_abc'
  AND completed_at < NOW() - INTERVAL '30 days'
  AND result_s3_key IS NOT NULL
  AND result_cleared_at IS NULL
LIMIT 10;
```

**Python으로 특정 runs만 삭제**:
```python
from dpp_api.storage.s3_client import get_s3_client

s3_client = get_s3_client()

# 수동으로 특정 runs의 S3 삭제
runs_to_clear = [...]  # 위 SQL로 조회한 runs

for run in runs_to_clear:
    s3_client.delete_object(
        bucket=run.result_s3_bucket,
        key=run.result_s3_key,
    )
    print(f"Deleted s3://{run.result_s3_bucket}/{run.result_s3_key}")

# DB 업데이트
repo = RunRepository(session)
repo.mark_results_cleared([run.run_id for run in runs_to_clear])
```

---

## 4. 복원 (Retention 삭제 후)

### 4.1. S3 삭제 후 복원 불가능

⚠️ **중요**: S3 result objects 삭제 후에는 복원 불가능합니다.

**백업 정책**:
- Retention cleanup 실행 전 S3 버킷에 **Lifecycle Policy** 설정 권장
- S3 Versioning 활성화 시 삭제된 객체 복원 가능 (비용 증가)

### 4.2. S3 Lifecycle Policy 예시

**S3 Lifecycle Rule** (Retention cleanup 대체):
```json
{
  "Rules": [
    {
      "Id": "DPP-Result-Expiration",
      "Status": "Enabled",
      "Filter": {
        "Prefix": "results/"
      },
      "Expiration": {
        "Days": 30
      }
    }
  ]
}
```

**주의**:
- S3 Lifecycle Policy 사용 시 DPP Retention Loop 비활성화 권장 (중복 방지)
- DB `result_cleared_at` 타임스탬프는 자동 업데이트되지 않음

---

## 5. 트러블슈팅

### 5.1. S3 삭제 실패 (권한 오류)

**에러**:
```
ERROR Failed to delete S3 object s3://dpp-results/run_abc123.json: AccessDenied
```

**해결**:
1. Reaper 서비스 IAM Role/Service Account에 S3 삭제 권한 추가:
   ```json
   {
     "Effect": "Allow",
     "Action": "s3:DeleteObject",
     "Resource": "arn:aws:s3:::dpp-results/*"
   }
   ```

2. 권한 적용 후 Reaper 재시작:
   ```bash
   kubectl rollout restart deployment/dpp-reaper -n dpp-production
   ```

### 5.2. 대량 삭제로 인한 성능 저하

**증상**: Retention Loop 실행 시 API 응답 느려짐

**원인**: S3 삭제 요청 과다

**해결**:
1. 배치 크기 축소 (기본값: 100):
   ```python
   # retention_loop.py 수정 또는 환경변수 추가
   batch_size = 50  # 한 번에 50개만 처리
   ```

2. 실행 간격 단축 + 배치 크기 축소:
   ```bash
   DPP_RETENTION_LOOP_INTERVAL_SECONDS=7200  # 2시간마다 실행
   ```

### 5.3. DB result_cleared_at 업데이트 누락

**증상**: S3는 삭제되었지만 DB `result_cleared_at`이 NULL

**확인**:
```sql
SELECT run_id, result_s3_key, result_cleared_at
FROM runs
WHERE status = 'COMPLETED'
  AND result_s3_key IS NOT NULL
  AND result_cleared_at IS NULL
LIMIT 10;
```

**수동 복구**:
```sql
-- 특정 run 수동 업데이트
UPDATE runs
SET result_cleared_at = NOW(), updated_at = NOW()
WHERE run_id = 'abc123';
```

---

## 6. 참고 자료

- Retention Loop 코드: `dpp/apps/reaper/dpp_reaper/loops/retention_loop.py`
- S3 Client: `dpp/apps/api/dpp_api/storage/s3_client.py`
- Run Repository: `dpp/apps/api/dpp_api/db/repo_runs.py`
- AWS S3 Lifecycle: [S3 Object Lifecycle Management](https://docs.aws.amazon.com/AmazonS3/latest/userguide/object-lifecycle-mgmt.html)

---

**마지막 업데이트**: 2026-02-17
**리뷰 주기**: 분기 1회 (Retention 정책 변경 시 즉시 업데이트)
