# RC Gates Execution Runbook

Doc ID: DP-RC-RUNBOOK-v0.4
Purpose: Step-by-step execution guide for RC validation and evidence archiving
Last Updated: 2026-02-15

---

## Overview

This runbook covers the complete RC validation flow:
1. **Local Double Run** (clean + rerun) for reproducibility
2. **CI External Repro** (workflow_dispatch) for independent verification
3. **Archive Evidence Pack** (local 2 + CI 1) for compliance/audit

**Target audience:** Release engineers, QA, compliance auditors

**Prerequisites:**
- Python 3.12+
- Docker + Docker Compose
- GitHub CLI (`gh`) authenticated
- On main/master branch (for CI trigger)

---

## Section A: Local Double Run (Clean + Rerun)

### Purpose
Execute RC gates twice locally to prove reproducibility:
1. **Clean run**: Full docker reset (volumes included) to simulate fresh environment
2. **Rerun**: Immediate re-execution without cleanup to catch state-dependent issues

### Commands (Mac/Linux)

```bash
cd /path/to/decisionproof

# 0) Capture baseline commit (for manifest)
git rev-parse HEAD

# 1) Clean: Compose full reset (volumes included)
docker compose -f infra/docker-compose.yml down --volumes --remove-orphans

# 2) Clean run
bash tools/run_rc_gates.sh

# 3) Rerun (no cleanup, immediate re-execution)
bash tools/run_rc_gates.sh
```

### Success Criteria
- Both runs complete without docker/pytest crashes
- Evidence directories created: `evidence/01_ci/<timestamp1>` and `evidence/01_ci/<timestamp2>`

### Check Results (PASS/FAIL Summary)

```bash
# Extract PASS/FAIL from latest 2 local runs
mapfile -t dirs < <(ls -1dt evidence/01_ci/* 2>/dev/null | head -2)
for d in "${dirs[@]}"; do
  echo "== $d =="
  line="$(grep -hE '^FAILED ' "$d/rc_run_stdout.log" "$d/rc_run_stderr.log" 2>/dev/null | head -1 || true)"
  if [ -n "$line" ]; then
    echo "FAIL: $(echo "$line" | awk '{print $2}')"
  else
    echo "PASS"
  fi
done
```

**If FAIL:**
1. Check first failed nodeid from output above
2. Inspect `evidence/01_ci/<timestamp>/rc_run_stdout.log` for full traceback
3. Check `evidence/01_ci/<timestamp>/dump_logs/` for docker service logs
4. Fix issue and repeat clean run

**If PASS (both runs):**
- Proceed to Section B (CI External Repro)

---

## Section B: CI External Repro (workflow_dispatch one-shot)

### Purpose
Trigger CI execution via `workflow_dispatch` to create external reproducibility evidence independent of local environment.

### Prerequisites
- `.github/workflows/rc_gates.yml` must be merged to main/master
- Current branch must be main/master (workflow_dispatch restriction)
- GitHub CLI authenticated: `gh auth status`

### Commands

```bash
# 1) Verify workflow exists on remote
gh workflow list

# Expected output should include: "RC Gates"

# 2) Trigger workflow_dispatch on main/master
gh workflow run "RC Gates" --ref main

# 3) Wait for workflow to register (5 seconds)
sleep 5

# 4) Get latest run ID
RUN_ID="$(gh run list -w "RC Gates" --limit 1 --json databaseId -q '.[0].databaseId')"
echo "CI Run ID: $RUN_ID"

# 5) Watch run until completion (blocks until done, exits non-zero if fail)
gh run watch "$RUN_ID" --exit-status

# 6) (Optional) Download artifact immediately for inspection
mkdir -p evidence_ci
gh run download "$RUN_ID" -D evidence_ci
```

### Success Criteria
- `gh run watch` exits with code 0 (PASS)
- Artifact is available for download

### Check Results

**If FAIL:**
1. View run in browser: `gh run view "$RUN_ID" --web`
2. Check "RC Gates (Linux)" job logs for first failed nodeid
3. Download artifact for detailed logs: `gh run download "$RUN_ID"`
4. Fix issue and re-trigger workflow_dispatch

**If PASS:**
- Proceed to Section C (Archive Evidence Pack)

---

## Section C: Archive Evidence Pack (local 2 + CI 1)

### Purpose
Bundle local 2 runs + CI 1 run into a single archive folder for compliance/audit:
- Archive path: `evidence/rc-v0.4-YYYYMMDD/`
- Includes: manifest.json, local/, ci/, docs_snapshot/

### Option 1: Manual Archive (Step-by-step)

```bash
cd /path/to/decisionproof

# Set CI run ID from Section B
export CI_RUN_ID=<run_id_from_section_b>

# Optional: Override defaults
export ARCHIVE_TAG="v0.4"          # Default: v0.4
export ARCHIVE_DATE="$(date +%Y%m%d)"  # Default: today

# Execute archive script
bash tools/archive_rc_evidence.sh
```

**Output:**
```
ARCHIVED: evidence/rc-v0.4-20260215/
```

**Archive structure:**
```
evidence/rc-v0.4-20260215/
├── manifest.json                   # Archive metadata (commit SHA, timestamps, run IDs)
├── local/
│   ├── 20260215_140122/           # Clean run evidence
│   │   ├── rc_run_cmd.txt
│   │   ├── rc_run_stdout.log
│   │   ├── rc_run_stderr.log
│   │   └── rc_run_env.txt
│   └── 20260215_140545/           # Rerun evidence
│       └── ...
├── ci/
│   └── run_1234567890/            # CI artifact (downloaded via gh run download)
│       └── rc-gates-<run_id>-1/
│           └── evidence/01_ci/...
└── docs_snapshot/
    ├── RC_MASTER_CHECKLIST.md
    ├── README_RC_GATES.md
    └── rc_gates.yml
```

### Option 2: Full Pipeline (All-in-one)

**Use this if starting from scratch (no local runs yet).**

```bash
cd /path/to/decisionproof

# Ensure you're on main/master
git checkout main
git pull

# Execute full pipeline (local 2x + CI trigger + archive)
bash tools/rc_double_then_ci_then_archive.sh
```

**This script will:**
1. Preflight checks (branch=main, workflow exists, gh auth)
2. Docker clean reset + clean run
3. Immediate rerun (no cleanup)
4. Verify both PASS (stops if FAIL)
5. Trigger CI workflow_dispatch
6. Wait for CI completion (blocks)
7. Auto-archive all evidence → `evidence/rc-v0.4-YYYYMMDD/`

**Success Criteria:**
- Script exits with code 0
- Archive directory created with all components
- Console output shows: `✅ FULL PIPELINE COMPLETE`

---

## Section D: Verification Checklist

After archiving, verify archive completeness:

```bash
ARCHIVE_DIR="evidence/rc-v0.4-$(date +%Y%m%d)"

# 1. Check manifest.json
cat "$ARCHIVE_DIR/manifest.json" | jq .

# Expected fields:
# - commit_sha
# - local_evidence_dirs (2 timestamps)
# - ci_run_id

# 2. Count local runs
ls -1 "$ARCHIVE_DIR/local" | wc -l
# Expected: 2

# 3. Verify CI artifact exists
ls -1 "$ARCHIVE_DIR/ci/"
# Expected: run_<ci_run_id>/

# 4. Check docs snapshot
ls "$ARCHIVE_DIR/docs_snapshot"
# Expected: RC_MASTER_CHECKLIST.md, README_RC_GATES.md, rc_gates.yml
```

---

## Section E: Common Issues and Troubleshooting

### Issue 1: Local Run Fails (Docker Connection)

**Symptoms:**
- `Cannot connect to Docker daemon`
- `connection refused` to postgres/redis

**Fix:**
```bash
# Restart Docker services
docker compose -f infra/docker-compose.yml down
docker compose -f infra/docker-compose.yml up -d

# Wait for healthy
docker compose -f infra/docker-compose.yml ps
# All services should show "(healthy)"
```

### Issue 2: CI Trigger Fails (Branch Restriction)

**Symptoms:**
- `gh workflow run` fails with "workflow not found"
- Script stops at preflight: "Must be on main/master branch"

**Fix:**
```bash
# Ensure workflow is merged to main
git checkout main
git pull

# Verify workflow exists on remote
gh workflow list | grep "RC Gates"
```

### Issue 3: Archive Script Fails (gh CLI)

**Symptoms:**
- `gh auth status` fails
- `gh run download` fails with permission error

**Fix:**
```bash
# Re-authenticate
gh auth login

# Verify scopes include repo access
gh auth status
```

### Issue 4: Less Than 2 Local Runs

**Symptoms:**
- Archive script warns: "Less than 2 local evidence directories found"

**Fix:**
```bash
# Run local double run again
docker compose -f infra/docker-compose.yml down --volumes --remove-orphans
bash tools/run_rc_gates.sh
bash tools/run_rc_gates.sh

# Then retry archive
```

---

## Section F: Quick Reference

### One-liner: Full Pipeline

```bash
git checkout main && git pull && bash tools/rc_double_then_ci_then_archive.sh
```

### One-liner: Check Latest 2 Local Runs

```bash
mapfile -t d < <(ls -1dt evidence/01_ci/* | head -2); for x in "${d[@]}"; do echo "== $x =="; grep -hE '^FAILED ' "$x"/*.log 2>/dev/null | head -1 || echo "PASS"; done
```

### One-liner: Manual Archive (After CI Done)

```bash
CI_RUN_ID=<your_ci_run_id> bash tools/archive_rc_evidence.sh
```

---

## Section G: Compliance Notes

**Audit Trail:**
- Archive path follows convention: `evidence/rc-<tag>-<YYYYMMDD>/`
- manifest.json includes commit SHA for traceability
- All timestamps in UTC (manifest) and local timezone (evidence folder names)

**Retention:**
- Local archives: Keep indefinitely (user decision)
- CI artifacts: 7 days default (configurable via workflow_dispatch)
- Recommendation: Copy archive to external storage for long-term retention

**SSOT Reference:**
- Archive creation documented in: RC_MASTER_CHECKLIST.md Section 4 (Evidence Pack)
- CI workflow source of truth: `.github/workflows/rc_gates.yml`

---

**End of Runbook**
