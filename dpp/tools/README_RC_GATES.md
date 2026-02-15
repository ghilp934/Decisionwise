# RC Gates One-shot Execution

## Usage

**Mac/Linux:**
```bash
cd /path/to/dpp
bash tools/run_rc_gates.sh
```

**Windows (PowerShell):**
```powershell
cd C:\path\to\dpp
powershell -ExecutionPolicy Bypass -File tools\run_rc_gates.ps1
```

## Output

All execution evidence is automatically saved to:
```
evidence/01_ci/<timestamp>/
├── rc_run_cmd.txt          # Exact pytest command executed
├── rc_run_stdout.log       # Test output
├── rc_run_stderr.log       # Error output
├── rc_run_env.txt          # Environment snapshot (Python/Docker/Compose versions)
└── dump_logs/              # Auto-generated on failure only
    ├── docker_compose_ps.txt
    ├── docker_postgres.log
    ├── docker_redis.log
    ├── docker_localstack.log
    └── docker_ps_all.txt
```

## Common Failures and Immediate Actions

### (A) Postgres/Redis Connection Failure

**Symptoms:**
- `connection refused`
- `could not connect to server`
- `redis connection error`

**Immediate Action:**
1. Check service status:
   ```bash
   docker compose -f infra/docker-compose.yml ps
   ```
2. View recent logs (last 200 lines):
   ```bash
   docker compose -f infra/docker-compose.yml logs --tail 200 --timestamps postgres
   docker compose -f infra/docker-compose.yml logs --tail 200 --timestamps redis
   docker compose -f infra/docker-compose.yml logs --tail 200 --timestamps localstack
   ```
3. Restart services if unhealthy:
   ```bash
   docker compose -f infra/docker-compose.yml down
   docker compose -f infra/docker-compose.yml up -d
   ```

### (B) Docker Daemon/Image Failure (RC-5)

**Symptoms:**
- `Cannot connect to the Docker daemon`
- `image not found: dpp-api:rc-test`
- `Error response from daemon`

**Immediate Action:**
1. Verify Docker is running:
   ```bash
   docker info
   ```
2. Check existing images:
   ```bash
   docker images | grep dpp
   ```
3. Rebuild required images:
   ```bash
   docker build -f Dockerfile.api -t dpp-api:rc-test .
   docker build -f Dockerfile.worker -t dpp-worker:rc-test .
   docker build -f Dockerfile.reaper -t dpp-reaper:rc-test .
   ```

### (C) Pytest Option Conflict

**Symptoms:**
- `pytest: error: unrecognized arguments: --cov`
- `pytest: error: unrecognized arguments: --xdist`

**Immediate Action:**
1. The script already includes `-o addopts=` to bypass `pytest.ini` / `pyproject.toml` addopts.
2. If error persists, check plugin installation:
   ```bash
   pip install -e '.[dev]'  # Reinstall dev dependencies
   ```
3. Manual fallback (without script):
   ```bash
   pytest -q -o addopts= --maxfail=1 \
     apps/api/tests/test_rc1_contract.py \
     apps/api/tests/test_rc2_error_format.py \
     apps/api/tests/test_rc3_rate_limit_headers.py \
     apps/api/tests/test_rc4_billing_invariants.py \
     apps/worker/tests/test_rc4_finalize_invariants.py \
     apps/api/tests/test_rc5_gate.py \
     apps/api/tests/test_rc6_observability.py \
     apps/api/tests/test_rc7_otel_contract.py \
     apps/api/tests/test_rc8_release_packet_gate.py \
     apps/api/tests/test_rc9_ops_pack_gate.py
   ```

## Script Behavior

- **Fail-fast:** Stops at first failure (`--maxfail=1`)
- **Auto-dump:** Captures Docker logs automatically on any failure
- **Deterministic:** Uses `-o addopts=` to ignore pytest.ini configuration
- **Evidence:** All runs create timestamped evidence folder, pass or fail

## Dependencies

- Python 3.12+
- Docker + Docker Compose
- pytest (installed via `pip install -e '.[dev]'`)
- Services: postgres, redis, localstack (auto-started by script)

## Troubleshooting

If script fails to execute:
1. Ensure you're in the repo root (`dpp/`)
2. Check script permissions (Mac/Linux): `chmod +x tools/run_rc_gates.sh`
3. Verify Docker is running: `docker ps`
4. Check Python environment: `python --version` (should be 3.12+)

For detailed RC acceptance criteria, see: `/docs/RC_ACCEPTANCE.md`

For complete execution workflow (local 2x + CI + archive), see: `/docs/rc/RC_RUNBOOK.md`

## CI Integration

RC Gates run automatically in GitHub Actions on every pull request and push to `master` or `release/**` branches. The CI workflow uses the same `tools/run_rc_gates.sh` script, ensuring identical behavior between local and CI environments.

**Evidence artifacts** are automatically uploaded to GitHub Actions artifacts (retention: 7 days by default) for every CI run, regardless of PASS/FAIL status. Download artifacts from the workflow run page to inspect test outputs and logs.

**PR comments** are automatically posted/updated on pull requests (non-fork only) with a summary of RC results, including the latest evidence directory path and the first failure nodeid (if any).

For manual CI runs with custom options, use the "workflow_dispatch" trigger in GitHub Actions UI.
