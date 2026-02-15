# Staging Dry Run Runbook

Doc ID: DP-STAGING-DRY-RUN-v0.4
Purpose: Execute staging deployment + smoke tests to validate release readiness
Last Updated: 2026-02-15

---

## Mechanism

**Deployment Type**: Kubernetes + kubectl

**Evidence**:
- `k8s/README.md` (Production-ready Kubernetes manifests for DPP API Platform v0.4.2.2)
- `k8s/deploy.sh` (Automated deployment script with kubectl rollout status)
- `k8s/namespace.yaml` (Namespace: dpp-production)

---

## Preconditions

### Required Tools
- `kubectl` (1.27+)
- `curl` (for smoke tests)
- `jq` (for JSON parsing)

### Required Access
- Kubernetes cluster access (staging context)
- kubectl config with valid credentials
- Namespace: `dpp-staging` (or as configured)

### Required Permissions
- `kubectl get`, `apply`, `rollout` in staging namespace
- `kubectl logs`, `describe` for debugging

---

## Inputs

Set these environment variables before execution:

```bash
# Required
export STAGING_CONTEXT="staging-cluster"        # kubectl context name
export STAGING_NAMESPACE="dpp-staging"          # Kubernetes namespace
export STAGING_BASE_URL="https://staging-api.decisionproof.ai"  # API base URL

# Optional (if images are pre-built)
export AWS_ACCOUNT_ID="123456789012"
export AWS_REGION="us-east-1"
export IMAGE_TAG="v0.4.2.2"  # Default: latest

# Optional (for authenticated smoke tests)
export STAGING_API_KEY="sk_test_..."  # Staging API key (if required)
```

**If inputs are not set**, the script will:
1. Check for inputs
2. Print required values and where to find them
3. Exit with error (no guessing)

---

## Step-by-Step Procedure

### 1. Preflight Check

```bash
# Verify kubectl access
kubectl --context="$STAGING_CONTEXT" get namespaces

# Verify namespace exists
kubectl --context="$STAGING_CONTEXT" get namespace "$STAGING_NAMESPACE"

# Capture current state (before deployment)
kubectl --context="$STAGING_CONTEXT" get deploy,po,svc -n "$STAGING_NAMESPACE" -o wide > evidence/staging/$(date +%Y%m%d)/deploy/status_before.txt
```

**Expected**: Namespace exists, kubectl has access

### 2. Deploy to Staging

```bash
# Set kubectl context
kubectl config use-context "$STAGING_CONTEXT"

# Deploy API (example using k8s manifests)
cat k8s/api-deployment.yaml | \
  sed "s/\${AWS_ACCOUNT_ID}/${AWS_ACCOUNT_ID}/g" | \
  sed "s/\${IMAGE_TAG}/${IMAGE_TAG}/g" | \
  kubectl apply -f -

# Deploy Worker
cat k8s/worker-deployment.yaml | \
  sed "s/\${AWS_ACCOUNT_ID}/${AWS_ACCOUNT_ID}/g" | \
  sed "s/\${IMAGE_TAG}/${IMAGE_TAG}/g" | \
  kubectl apply -f -

# Deploy Reaper
cat k8s/reaper-deployment.yaml | \
  sed "s/\${AWS_ACCOUNT_ID}/${AWS_ACCOUNT_ID}/g" | \
  sed "s/\${IMAGE_TAG}/${IMAGE_TAG}/g" | \
  kubectl apply -f -
```

### 3. Wait for Rollout

```bash
# Wait for API rollout (timeout: 5 minutes)
kubectl rollout status deployment/dpp-api -n "$STAGING_NAMESPACE" --timeout=5m

# Wait for Worker rollout
kubectl rollout status deployment/dpp-worker -n "$STAGING_NAMESPACE" --timeout=5m

# Wait for Reaper rollout
kubectl rollout status deployment/dpp-reaper -n "$STAGING_NAMESPACE" --timeout=5m
```

**Expected**: All deployments report "successfully rolled out"

### 4. Capture Post-Deploy State

```bash
kubectl --context="$STAGING_CONTEXT" get deploy,po,svc -n "$STAGING_NAMESPACE" -o wide > evidence/staging/$(date +%Y%m%d)/deploy/status_after.txt
```

### 5. Execute Smoke Tests

Run the automated smoke test suite (10 checks):

```bash
bash tools/staging_dry_run.sh
```

**Smoke Test Suite** (see Section: Smoke Test Definition below):
1. GET /health (200)
2. GET /readyz (200)
3. GET /.well-known/openapi.json (200)
4. GET /llms.txt (200)
5. GET /api-docs (200, Swagger UI)
6. GET /redoc (200, ReDoc)
7. GET /metrics (200, Prometheus)
8. GET /pricing/ssot.json (200)
9. GET /docs/quickstart.md (200)
10. GET /v1/runs (401 if unauthenticated, 200 if authenticated)

**Expected**: 10/10 PASS

---

## Stop Rules

**Immediately STOP if**:
1. `kubectl rollout status` fails (deployment did not converge)
2. Any pod in `CrashLoopBackOff` or `Error` state
3. Health check (`/health` or `/readyz`) returns non-200 after 2 minutes
4. Smoke tests: < 8/10 PASS (80% threshold)

**Action on STOP**:
1. Do NOT proceed to further testing
2. Capture logs: `kubectl logs`, `kubectl describe`, `kubectl get events`
3. Save to `evidence/staging/YYYYMMDD/dump_logs/`
4. Exit with non-zero code

---

## Evidence Checklist

After successful run, verify these files exist in `evidence/staging/YYYYMMDD/`:

```
evidence/staging/20260215/
├── manifest.json                    # Summary (ok: true/false, duration, etc.)
├── preflight/
│   ├── versions.txt                 # git SHA, kubectl version, context
│   └── target.txt                   # Namespace, base URL, deployments
├── deploy/
│   ├── cmd.txt                      # Deployment commands executed
│   ├── stdout.log                   # kubectl output
│   ├── stderr.log                   # kubectl errors (if any)
│   ├── status_before.txt            # Pre-deploy state
│   └── status_after.txt             # Post-deploy state
├── smoke/
│   ├── cmd.txt                      # Smoke test commands
│   ├── results.json                 # 10 checks: pass/fail + http status + latency
│   └── http_samples.log             # Sample requests/responses (2-3 examples)
└── dump_logs/                       # (Only if failure)
    ├── k8s_describe.txt             # kubectl describe deployment/pod
    ├── k8s_events.txt               # kubectl get events
    └── app_logs_tail.txt            # kubectl logs (last 200 lines)
```

---

## Success Criteria

**Deployment Success**:
- [ ] `kubectl rollout status` exits 0 for all deployments (API, Worker, Reaper)
- [ ] All pods in `Running` state (0 restarts preferred)
- [ ] Services have endpoints assigned

**Smoke Test Success**:
- [ ] 10/10 checks PASS
- [ ] `/health` returns `{"status": "healthy", "version": "0.4.2.2"}`
- [ ] `/readyz` returns `{"status": "ready", ...}` with all services "up"
- [ ] No 5xx errors in smoke tests

**Evidence Success**:
- [ ] `manifest.json` has `deploy.ok: true` and `smoke.ok: true`
- [ ] All required files in `evidence/staging/YYYYMMDD/` present

---

## Smoke Test Definition

### Test Suite (10 Checks)

Based on `apps/api/dpp_api/routers/health.py` and `apps/api/dpp_api/main.py`:

| # | Method | Endpoint | Expected Status | Notes |
|---|--------|----------|-----------------|-------|
| 1 | GET | /health | 200 | Always returns healthy (basic liveness) |
| 2 | GET | /readyz | 200 | Dependency check (503 if down) |
| 3 | GET | /.well-known/openapi.json | 200 | OpenAPI spec |
| 4 | GET | /llms.txt | 200 | AI tooling documentation |
| 5 | GET | /api-docs | 200 | Swagger UI (HTML) |
| 6 | GET | /redoc | 200 | ReDoc (HTML) |
| 7 | GET | /metrics | 200 | Prometheus metrics (port 9090) |
| 8 | GET | /pricing/ssot.json | 200 | Pricing SSOT |
| 9 | GET | /docs/quickstart.md | 200 | Quickstart doc |
| 10 | GET | /v1/runs | 401 or 200 | 401 if no auth, 200 if valid API key |

**Evidence**:
- `apps/api/dpp_api/routers/health.py` (lines 105-123: /health, lines 126-158: /readyz)
- `apps/api/dpp_api/main.py` (lines 28-40: FastAPI app with /api-docs, /redoc)
- `k8s/README.md` (lines 146-157: health and readiness endpoints)

**Latency Threshold** (informational, not blocking):
- p95 < 500ms for health/readyz
- p95 < 1000ms for openapi/docs

---

## Troubleshooting

### Issue: Rollout Timeout

**Symptoms**: `kubectl rollout status` hangs or times out

**Check**:
```bash
kubectl get pods -n "$STAGING_NAMESPACE"
kubectl describe pod <pod-name> -n "$STAGING_NAMESPACE"
kubectl get events -n "$STAGING_NAMESPACE" --sort-by='.lastTimestamp' | tail -20
```

**Common Causes**:
- Image pull errors (ImagePullBackOff)
- Insufficient resources (Pending)
- Liveness/readiness probe failures

### Issue: /readyz Returns 503

**Symptoms**: `/readyz` returns `{"status": "not_ready", ...}`

**Check**:
```bash
curl "$STAGING_BASE_URL/health" | jq '.services'
# Check which service is "down"
```

**Common Causes**:
- Database connection failure
- Redis connection failure
- S3/SQS endpoint misconfiguration

### Issue: Smoke Tests Fail (< 10/10)

**Symptoms**: `smoke/results.json` shows failures

**Check**:
```bash
cat evidence/staging/YYYYMMDD/smoke/results.json | jq '.checks[] | select(.pass == false)'
```

**Common Causes**:
- LoadBalancer endpoint not ready (wait 1-2 minutes)
- Ingress/ALB misconfiguration
- CORS issues (check browser console if applicable)

---

**End of Runbook**
