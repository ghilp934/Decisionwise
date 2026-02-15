# Rollback Drill Runbook

Doc ID: DP-ROLLBACK-DRILL-v0.4
Purpose: Practice rollback procedure to previous Known-Good state
Last Updated: 2026-02-15

---

## Mechanism

**Deployment Type**: Kubernetes + kubectl

**Rollback Method**: `kubectl rollout undo`

**Evidence**:
- `k8s/README.md` (lines 201-214: Rolling Updates section with rollback example)
- `ops/runbook.md` (lines 48-55: Rollback Procedure)

---

## Preconditions

### Required Tools
- `kubectl` (1.27+)
- `curl` (for post-rollback smoke tests)
- `jq` (for JSON parsing)

### Required Access
- Kubernetes cluster access (staging context)
- kubectl config with valid credentials
- Namespace: `dpp-staging` (or as configured)

### Required Permissions
- `kubectl rollout undo` in staging namespace
- `kubectl rollout history` to view revisions

### Prerequisites
- **At least 1 previous deployment exists** (revision > 1)
  - Check: `kubectl rollout history deployment/dpp-api -n <namespace>`
  - If revision = 1, perform a dummy deploy first to create revision 2

---

## Inputs

Set these environment variables before execution:

```bash
# Required
export STAGING_CONTEXT="staging-cluster"        # kubectl context name
export STAGING_NAMESPACE="dpp-staging"          # Kubernetes namespace
export STAGING_BASE_URL="https://staging-api.decisionproof.ai"  # API base URL

# Optional (rollback target)
export ROLLBACK_REVISION=""  # Leave empty to rollback to previous (n-1)
                            # Or set to specific revision number
```

**If inputs are not set**, the script will:
1. Print required values and where to find them
2. Exit with error (no guessing)

---

## Known-Good Definition

**For Kubernetes Deployments**:
- **Known-Good** = Previous ReplicaSet revision (n-1)
- Verified via: `kubectl rollout history deployment/<name> -n <namespace>`

**Revision Selection**:
- Default: Rollback to **previous revision** (n-1)
  - Command: `kubectl rollout undo deployment/<name>`
- Specific: Rollback to **specific revision** (if known)
  - Command: `kubectl rollout undo deployment/<name> --to-revision=<N>`

**Evidence Location**:
- k8s/README.md (lines 212-214): `kubectl rollout undo deployment/dpp-api -n dpp-production`
- ops/runbook.md (lines 48-55): Rollback Procedure with kubectl rollout undo

---

## Step-by-Step Procedure

### 1. Preflight Check (Capture Current State)

```bash
# Set kubectl context
kubectl config use-context "$STAGING_CONTEXT"

# Check rollout history (must have revision > 1)
kubectl rollout history deployment/dpp-api -n "$STAGING_NAMESPACE"
kubectl rollout history deployment/dpp-worker -n "$STAGING_NAMESPACE"
kubectl rollout history deployment/dpp-reaper -n "$STAGING_NAMESPACE"

# Capture current state (before rollback)
kubectl get deploy,po,svc -n "$STAGING_NAMESPACE" -o wide > evidence/staging/$(date +%Y%m%d)/rollback/status_before.txt

# Capture current revision numbers
kubectl get deployment dpp-api -n "$STAGING_NAMESPACE" -o jsonpath='{.metadata.annotations.deployment\.kubernetes\.io/revision}' > evidence/staging/$(date +%Y%m%d)/rollback/revision_before_api.txt
kubectl get deployment dpp-worker -n "$STAGING_NAMESPACE" -o jsonpath='{.metadata.annotations.deployment\.kubernetes\.io/revision}' > evidence/staging/$(date +%Y%m%d)/rollback/revision_before_worker.txt
kubectl get deployment dpp-reaper -n "$STAGING_NAMESPACE" -o jsonpath='{.metadata.annotations.deployment\.kubernetes\.io/revision}' > evidence/staging/$(date +%Y%m%d)/rollback/revision_before_reaper.txt
```

**Expected**: Each deployment has revision >= 2

**If revision = 1**: Abort and notify user to perform a deployment first

### 2. Execute Rollback

```bash
# Rollback API
if [ -z "$ROLLBACK_REVISION" ]; then
  # Rollback to previous (n-1)
  kubectl rollout undo deployment/dpp-api -n "$STAGING_NAMESPACE"
else
  # Rollback to specific revision
  kubectl rollout undo deployment/dpp-api -n "$STAGING_NAMESPACE" --to-revision="$ROLLBACK_REVISION"
fi

# Rollback Worker
if [ -z "$ROLLBACK_REVISION" ]; then
  kubectl rollout undo deployment/dpp-worker -n "$STAGING_NAMESPACE"
else
  kubectl rollout undo deployment/dpp-worker -n "$STAGING_NAMESPACE" --to-revision="$ROLLBACK_REVISION"
fi

# Rollback Reaper
if [ -z "$ROLLBACK_REVISION" ]; then
  kubectl rollout undo deployment/dpp-reaper -n "$STAGING_NAMESPACE"
else
  kubectl rollout undo deployment/dpp-reaper -n "$STAGING_NAMESPACE" --to-revision="$ROLLBACK_REVISION"
fi
```

### 3. Wait for Rollback Completion

```bash
# Wait for API rollback (timeout: 5 minutes)
kubectl rollout status deployment/dpp-api -n "$STAGING_NAMESPACE" --timeout=5m

# Wait for Worker rollback
kubectl rollout status deployment/dpp-worker -n "$STAGING_NAMESPACE" --timeout=5m

# Wait for Reaper rollback
kubectl rollout status deployment/dpp-reaper -n "$STAGING_NAMESPACE" --timeout=5m
```

**Expected**: All rollouts report "successfully rolled out"

### 4. Verify Rollback Success

```bash
# Capture post-rollback state
kubectl get deploy,po,svc -n "$STAGING_NAMESPACE" -o wide > evidence/staging/$(date +%Y%m%d)/rollback/status_after.txt

# Capture new revision numbers (should be previous - 1 or target revision)
kubectl get deployment dpp-api -n "$STAGING_NAMESPACE" -o jsonpath='{.metadata.annotations.deployment\.kubernetes\.io/revision}' > evidence/staging/$(date +%Y%m%d)/rollback/revision_after_api.txt
kubectl get deployment dpp-worker -n "$STAGING_NAMESPACE" -o jsonpath='{.metadata.annotations.deployment\.kubernetes\.io/revision}' > evidence/staging/$(date +%Y%m%d)/rollback/revision_after_worker.txt
kubectl get deployment dpp-reaper -n "$STAGING_NAMESPACE" -o jsonpath='{.metadata.annotations.deployment\.kubernetes\.io/revision}' > evidence/staging/$(date +%Y%m%d)/rollback/revision_after_reaper.txt

# Verify revision changed
diff evidence/staging/$(date +%Y%m%d)/rollback/revision_before_api.txt evidence/staging/$(date +%Y%m%d)/rollback/revision_after_api.txt || echo "API revision changed (expected)"
```

**Expected**: Revision numbers differ (rollback occurred)

### 5. Re-run Smoke Tests (MANDATORY)

**After rollback, re-run the same 10 smoke tests** to verify Known-Good state is functional:

```bash
bash tools/rollback_drill.sh
```

**Expected**: 10/10 PASS (same as staging_dry_run)

---

## Stop Rules

**Immediately STOP if**:
1. Preflight check fails (revision < 2, no previous deployment exists)
2. `kubectl rollout undo` fails (permission denied, deployment not found)
3. `kubectl rollout status` fails after rollback (pods not converging)
4. Post-rollback smoke tests: < 8/10 PASS (80% threshold)

**Action on STOP**:
1. Do NOT proceed further
2. Capture logs: `kubectl logs`, `kubectl describe`, `kubectl get events`
3. Save to `evidence/staging/YYYYMMDD/dump_logs/`
4. **Consider rollback to even earlier revision** (n-2) if n-1 is also broken
5. Exit with non-zero code

---

## Evidence Checklist

After successful rollback drill, verify these files exist in `evidence/staging/YYYYMMDD/`:

```
evidence/staging/20260215/
├── manifest.json                    # Summary (rollback.ok: true/false)
├── rollback/
│   ├── cmd.txt                      # Rollback commands executed
│   ├── stdout.log                   # kubectl output
│   ├── stderr.log                   # kubectl errors (if any)
│   ├── status_before.txt            # Pre-rollback state
│   ├── status_after.txt             # Post-rollback state
│   ├── revision_before_api.txt      # API revision before rollback
│   ├── revision_after_api.txt       # API revision after rollback (should differ)
│   ├── revision_before_worker.txt
│   ├── revision_after_worker.txt
│   ├── revision_before_reaper.txt
│   └── revision_after_reaper.txt
├── smoke/
│   ├── results_post_rollback.json   # Re-run smoke tests (10 checks)
│   └── http_samples_post_rollback.log
└── dump_logs/                       # (Only if failure)
    ├── k8s_describe.txt
    ├── k8s_events.txt
    └── app_logs_tail.txt
```

---

## Success Criteria

**Rollback Execution Success**:
- [ ] `kubectl rollout undo` exits 0 for all deployments (API, Worker, Reaper)
- [ ] `kubectl rollout status` exits 0 (all pods converged)
- [ ] All pods in `Running` state

**Rollback Verification Success**:
- [ ] Revision numbers changed (before != after)
- [ ] If rollback to n-1: revision_after = revision_before - 1
- [ ] If rollback to specific: revision_after = target revision
- [ ] `kubectl rollout history` confirms rollback occurred

**Post-Rollback Smoke Test Success**:
- [ ] 10/10 checks PASS
- [ ] `/health` returns `{"status": "healthy", "version": "0.4.2.2"}`
- [ ] `/readyz` returns `{"status": "ready", ...}` with all services "up"

**Evidence Success**:
- [ ] `manifest.json` has `rollback.ok: true` and `smoke.ok: true` (post-rollback)
- [ ] All required files in `evidence/staging/YYYYMMDD/rollback/` present

---

## Troubleshooting

### Issue: Rollback Fails (No Previous Revision)

**Symptoms**: `kubectl rollout undo` returns "no rollout history found"

**Cause**: Only 1 revision exists (initial deployment)

**Fix**:
1. Perform a dummy deployment to create revision 2
2. Then retry rollback drill

### Issue: Rollback Completes but Pods CrashLoop

**Symptoms**: `kubectl rollout status` succeeds, but pods restart repeatedly

**Cause**: Previous revision (n-1) is also broken

**Fix**:
```bash
# Check rollout history
kubectl rollout history deployment/dpp-api -n "$STAGING_NAMESPACE"

# Rollback to older revision (n-2 or earlier)
kubectl rollout undo deployment/dpp-api -n "$STAGING_NAMESPACE" --to-revision=<older_revision>
```

### Issue: Post-Rollback Smoke Tests Fail

**Symptoms**: Smoke tests pass during dry run, but fail after rollback

**Cause**: Known-Good revision may have different configuration or incompatible schema

**Fix**:
1. Check pod logs: `kubectl logs -l app=dpp-api -n "$STAGING_NAMESPACE" --tail=100`
2. Check events: `kubectl get events -n "$STAGING_NAMESPACE" --sort-by='.lastTimestamp'`
3. If schema mismatch: may need database migration rollback (manual, out of scope)

---

## Notes

**Kubernetes Rollback Behavior**:
- Rollback creates a **new revision** (e.g., if current is rev 3, rollback to rev 2 creates rev 4 with rev 2's template)
- Rollback history is preserved (can rollback to any previous revision)
- Max revisions: controlled by `spec.revisionHistoryLimit` (default 10)

**When to Use Specific Revision**:
- Use `--to-revision=N` when you know which revision is Known-Good
- Example: Current is rev 5 (broken), rev 4 (broken), rev 3 (known-good)
  - Command: `kubectl rollout undo --to-revision=3`

**Production Rollback**:
- In production, rollback should be automated (CI/CD pipeline + monitoring)
- This drill is for **practice and verification** only
- Never rollback production without:
  1. Incident commander approval
  2. Postmortem tracking (ticket/doc)
  3. Automated smoke tests passing

---

**End of Runbook**
