# DPP Pilot Overlay — 배포 당일 절차

## SSOT 값 관리

운영 값(`HOST`, `ACM ARN`, `SG ID`, `APP_HOST`)은 **`pilot.params.yaml` 1곳만 수정**하면 됩니다.
수정 후 아래 명령으로 ingress/configmap을 자동 동기화하세요.

```bash
# 1. pilot.params.yaml 수정 (SSOT)
# 2. 동기화 실행 (ingress-pilot.yaml + patch-configmap-pilot.yaml 자동 업데이트)
./sync_pilot_values.sh
# 3. PRE-GATE 검증 (params ↔ ingress 동일성 포함)
./pre_gate_check.sh
```

## 사전조건

1. **운영 값 확정** (PRE-GATE 통과 조건):
   - `pilot.params.yaml` 수정: `PILOT_HOST`, `PILOT_APP_HOST`, `PILOT_ACM_CERT_ARN`, `PILOT_ALB_SECURITY_GROUP_ID`
   - `./sync_pilot_values.sh` 실행 → `ingress-pilot.yaml`, `patch-configmap-pilot.yaml` 자동 업데이트

2. **dpp-supabase-ca ConfigMap 준비** (운영자가 인증서 파일 제공):
   ```bash
   kubectl create configmap dpp-supabase-ca \
     --from-file=supabase-ca.crt=/path/to/supabase-ca.crt \
     -n dpp-pilot
   ```
   > ⚠️ repo에 인증서 파일이 없으므로 운영자가 별도 제공해야 합니다.

3. **SecretProviderClass 전제조건**:
   - Secrets Store CSI Driver 설치 완료 (kube-system)
   - AWS Provider 설치 완료
   - AWS Secrets Manager에 `decisionproof/pilot/dpp-secrets` JSON secret 생성 완료
   > ⚠️ `secretObjects`(K8s Secret sync)는 **Pod가 CSI 볼륨을 실제로 마운트해야** 동작합니다.
   > Pod 없이 `kubectl apply`만으로는 `dpp-secrets` Secret이 생성되지 않습니다.

---

## Kube-Context Guard (필수)

배포 전 `pilot_cutover.env`의 `EXPECTED_KUBE_CONTEXT`를 실제 컨텍스트 이름으로 확정해야 합니다.
`pilot_cutover_execute.sh`는 시작 시 현재 컨텍스트와 비교하며, 불일치 시 즉시 FAIL 합니다.
**원클릭 실행**: `./pilot_cutover_execute.sh` (sync → gate → DB → deploy → rollout 자동 진행)

---

## 배포 당일 커맨드 (6단계)

```bash
# Step 1: PRE-GATE 통과 확인 (REPLACE_ME_* 모두 채운 후 실행)
./pre_gate_check.sh

# Step 2: (사전조건) dpp-pilot 네임스페이스에 dpp-supabase-ca ConfigMap 준비
#         kubectl create configmap dpp-supabase-ca --from-file=supabase-ca.crt=... -n dpp-pilot

# Step 3: Deploy 1단계 — DB 마이그레이션
kubectl apply -n dpp-pilot -f job-alembic-migrate.yaml
kubectl wait -n dpp-pilot --for=condition=complete --timeout=600s job/alembic-migrate
# 실패 시: kubectl logs -n dpp-pilot job/alembic-migrate --tail=200

# Step 4: Deploy 2단계 — App 배포 (단 한 줄)
kubectl apply -k .

# Step 5: Rollout 상태 확인
kubectl rollout status deployment/dpp-api -n dpp-pilot
kubectl rollout status deployment/dpp-reaper -n dpp-pilot
kubectl rollout status deployment/dpp-worker -n dpp-pilot
```

---

## Deployment Profile 비교

| Resource | Production | Pilot |
|----------|------------|-------|
| **Namespace** | `dpp-production` | `dpp-pilot` |
| **API replicas** | 3 | 1 |
| **Worker replicas (HPA)** | 2-5 | 1-3 |
| **Worker CPU req/limit** | 1000m / 2000m | 1000m / 2000m |
| **Worker Memory req/limit** | 2Gi / 4Gi | 1Gi / 2Gi |
| **SQS Queue** | dpp-runs-production | dpp-runs-pilot |
| **S3 Bucket** | dpp-results-production | dpp-results-pilot |
| **SM Secret path** | decisionproof/prod/dpp-secrets | decisionproof/pilot/dpp-secrets |
| **WORM Mode** | COMPLIANCE | GOVERNANCE |
