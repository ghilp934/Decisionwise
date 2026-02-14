# RC-2 Final Verification Guide
## Cross-Platform & Real-World Smoke Test

**Project**: Decisionproof API Platform
**Release Candidate**: RC-2 (RFC 9457 Problem Details)
**Status**: Local Tests PASSED (Windows) — Awaiting Cross-Platform Verification
**Date**: 2026-02-15

---

## Overview

This guide provides commands to verify RC-2 compliance in:
1. **Linux Environment** (Docker simulation for CI/Production parity)
2. **Real-World HTTP Stack** (Curl smoke test for header integrity)

**Why This Matters:**
- RC gates require **cross-platform proof** before lock.
- Middleware (uvicorn/nginx) can strip/mangle headers.
- Path separators and case sensitivity differ between Windows/Linux.

---

## CHECK 1: Linux Environment Simulation (Docker)

### Objective
Verify that RC-2 tests pass in a Linux container (python:3.11-slim) to catch:
- Path separator issues (Windows `\` vs Linux `/`)
- Case-sensitive import errors
- Line ending differences (CRLF vs LF)

### Prerequisites
- Docker installed and running
- Current working directory: `/dpp` (project root)

### Commands

#### Option A: Using Docker with pyproject.toml

```bash
# Navigate to project root
cd /path/to/dpp

# Run tests in Linux container
docker run --rm \
  -v "$(pwd):/app" \
  -w /app \
  python:3.11-slim \
  bash -c "
    pip install --quiet --upgrade pip && \
    pip install --quiet -e '.[test]' && \
    pytest apps/api/tests/test_rc2_error_format.py -v --tb=short
  "
```

**Expected Output:**
```
============================= test session starts =============================
platform linux -- Python 3.11.x, pytest-9.0.2
...
apps/api/tests/test_rc2_error_format.py::TestRC2ErrorFormat::test_401_unauthorized PASSED
apps/api/tests/test_rc2_error_format.py::TestRC2ErrorFormat::test_403_forbidden PASSED
apps/api/tests/test_rc2_error_format.py::TestRC2ErrorFormat::test_402_payment_required PASSED
apps/api/tests/test_rc2_error_format.py::TestRC2ErrorFormat::test_409_conflict PASSED
apps/api/tests/test_rc2_error_format.py::TestRC2ErrorFormat::test_422_validation_error PASSED
apps/api/tests/test_rc2_error_format.py::TestRC2ErrorFormat::test_429_rate_limit_exceeded PASSED
apps/api/tests/test_rc2_error_format.py::TestRC2ErrorFormat::test_429_retry_after_header PASSED
apps/api/tests/test_rc2_error_format.py::TestRC2InstanceFormat::test_instance_no_path_leak PASSED
apps/api/tests/test_rc2_error_format.py::TestRC2InstanceFormat::test_instance_no_numeric_only PASSED

============================= 9 passed in X.XXs ==============================
```

#### Option B: Using Docker with Minimal Dependencies

If `pip install -e '.[test]'` fails, use explicit dependencies:

```bash
docker run --rm \
  -v "$(pwd):/app" \
  -w /app \
  python:3.11-slim \
  bash -c "
    pip install --quiet fastapi uvicorn pytest pydantic sqlalchemy psycopg2-binary redis && \
    pytest apps/api/tests/test_rc2_error_format.py -v
  "
```

### Windows (PowerShell) Variant

```powershell
# Navigate to project root
cd C:\path\to\dpp

# Run tests in Linux container
docker run --rm `
  -v "${PWD}:/app" `
  -w /app `
  python:3.11-slim `
  bash -c "
    pip install --quiet --upgrade pip && \
    pip install --quiet -e '.[test]' && \
    pytest apps/api/tests/test_rc2_error_format.py -v --tb=short
  "
```

### What We're Testing

**Linux-Specific Bugs to Catch:**

1. **Path Separators**
   ```python
   # Windows: C:\Users\...\dpp_api\main.py
   # Linux:   /app/dpp_api/main.py
   # Catch: Hardcoded backslashes in imports
   ```

2. **Case Sensitivity**
   ```python
   # Windows: import from "DPP_API.Main" works
   # Linux:   Must be exact: "dpp_api.main"
   # Catch: Mismatched case in module names
   ```

3. **Line Endings**
   ```python
   # Windows: CRLF (\r\n)
   # Linux:   LF (\n)
   # Catch: Parser errors if not normalized
   ```

4. **File Permissions**
   ```bash
   # Linux containers run as root by default
   # Catch: Permission-related import failures
   ```

---

## CHECK 2: Real-World Smoke Test (Curl)

### Objective
Verify that uvicorn doesn't strip/mangle `Retry-After` headers and that Problem Details JSON is correctly formatted.

### Prerequisites
- Server can bind to localhost:8000
- `curl` installed (or use PowerShell's `Invoke-WebRequest`)

### Step 1: Start the Server

```bash
# Terminal 1: Start uvicorn
cd /path/to/dpp
uvicorn dpp_api.main:app --host 127.0.0.1 --port 8000 --reload
```

**Expected Output:**
```
INFO:     Uvicorn running on http://127.0.0.1:8000 (Press CTRL+C to quit)
INFO:     Started reloader process [12345] using StatReload
INFO:     Started server process [12346]
INFO:     Waiting for application startup.
INFO:     Application startup complete.
```

### Step 2: Trigger 429 with Curl

**Strategy**: Create a test endpoint that always returns 429, OR rapidly hit an endpoint with low rate limit.

#### Option A: Hit Health Endpoint Rapidly (No Auth Required)

```bash
# Terminal 2: Send rapid requests to trigger rate limit
# Note: /health may not have rate limits. Use a custom test route if needed.

for i in {1..100}; do
  curl -s -o /dev/null -w "%{http_code}\n" http://127.0.0.1:8000/health
done
```

#### Option B: Use Test Route (Recommended)

Create a test-only route that always returns 429:

```python
# Add to dpp_api/main.py temporarily:

@app.get("/test/rate-limit-429")
async def test_rate_limit_429():
    """Test endpoint that always returns 429 with Retry-After."""
    raise HTTPException(status_code=429, detail="Test rate limit exceeded")
```

Then test with curl:

```bash
# Test 429 response with full headers
curl -i http://127.0.0.1:8000/test/rate-limit-429

# OR use verbose mode
curl -v http://127.0.0.1:8000/test/rate-limit-429
```

#### Option C: Windows PowerShell Variant

```powershell
# PowerShell: Test 429 response
Invoke-WebRequest -Uri "http://127.0.0.1:8000/test/rate-limit-429" -Method GET | Select-Object StatusCode, Headers, Content
```

### Step 3: Verify Response

**Expected Output (curl -i):**

```http
HTTP/1.1 429 Too Many Requests
date: Fri, 15 Feb 2026 12:34:56 GMT
server: uvicorn
content-length: 234
content-type: application/problem+json
retry-after: 60
x-request-id: a1b2c3d4-e5f6-7890-abcd-ef1234567890

{
  "type": "https://api.decisionproof.ai/problems/http-429",
  "title": "Too Many Requests",
  "status": 429,
  "detail": "Test rate limit exceeded",
  "instance": "urn:decisionproof:trace:a1b2c3d4-e5f6-7890-abcd-ef1234567890"
}
```

### Verification Checklist

✅ **Status Code**: `429 Too Many Requests`
✅ **Content-Type**: `application/problem+json` (exact match)
✅ **Retry-After Header**: Present with integer value (e.g., `60`)
✅ **Problem Details Body**:
   - `type`: Valid URI
   - `title`: "Too Many Requests"
   - `status`: 429
   - `detail`: Descriptive message
   - `instance`: Opaque URN format (no "/" or numeric-only)

### Common Failure Modes

**❌ Retry-After Missing**
- **Cause**: Middleware stripped header
- **Fix**: Check CORS/proxy configs

**❌ Content-Type is `application/json`**
- **Cause**: Global exception handler not applied
- **Fix**: Verify handler registration in main.py

**❌ Instance Contains Path**
- **Cause**: Hardcoded `request.url.path` still exists
- **Fix**: Review usage.py and other routers

---

## Advanced: Full Stack Smoke Test Script

### Bash Script (Linux/macOS/WSL)

```bash
#!/bin/bash
# rc2_smoke_test.sh

set -e

echo "🚀 RC-2 Smoke Test - Starting Server..."

# Start server in background
uvicorn dpp_api.main:app --host 127.0.0.1 --port 8000 &
SERVER_PID=$!

# Wait for server to start
sleep 3

echo "✅ Server started (PID: $SERVER_PID)"
echo ""

# Test 429 endpoint
echo "🧪 Testing 429 Rate Limit..."
RESPONSE=$(curl -s -i http://127.0.0.1:8000/test/rate-limit-429)

# Check status code
if echo "$RESPONSE" | grep -q "429 Too Many Requests"; then
  echo "✅ Status: 429 OK"
else
  echo "❌ Status: FAIL (expected 429)"
fi

# Check Retry-After header
if echo "$RESPONSE" | grep -qi "retry-after:"; then
  RETRY_AFTER=$(echo "$RESPONSE" | grep -i "retry-after:" | awk '{print $2}' | tr -d '\r')
  echo "✅ Retry-After: $RETRY_AFTER seconds"
else
  echo "❌ Retry-After: MISSING"
fi

# Check Content-Type
if echo "$RESPONSE" | grep -q "application/problem+json"; then
  echo "✅ Content-Type: application/problem+json"
else
  echo "❌ Content-Type: FAIL"
fi

# Check instance format
if echo "$RESPONSE" | grep -q '"instance":"urn:decisionproof:trace:'; then
  echo "✅ Instance: Opaque URN format"
else
  echo "❌ Instance: FAIL (not opaque)"
fi

echo ""
echo "🛑 Stopping server..."
kill $SERVER_PID

echo "✅ RC-2 Smoke Test Complete"
```

### Windows Batch Script

```batch
@echo off
REM rc2_smoke_test.bat

echo Starting RC-2 Smoke Test...

REM Start server in background
start /B uvicorn dpp_api.main:app --host 127.0.0.1 --port 8000

REM Wait for server to start
timeout /t 5 /nobreak >nul

echo Testing 429 endpoint...
curl -i http://127.0.0.1:8000/test/rate-limit-429

echo.
echo Press any key to stop server...
pause >nul

REM Kill uvicorn process
taskkill /F /IM uvicorn.exe

echo RC-2 Smoke Test Complete
```

---

## Troubleshooting

### Docker Issues

**Error**: `Cannot connect to the Docker daemon`
```bash
# Solution: Start Docker Desktop or daemon
sudo systemctl start docker  # Linux
# OR restart Docker Desktop (Windows/Mac)
```

**Error**: `Permission denied` in container
```bash
# Solution: Run container as current user
docker run --rm --user $(id -u):$(id -g) ...
```

### Curl Issues

**Error**: `Failed to connect to localhost:8000`
```bash
# Solution 1: Check if server is running
ps aux | grep uvicorn

# Solution 2: Check if port is in use
netstat -ano | findstr :8000  # Windows
lsof -i :8000                  # Linux/Mac
```

**Error**: `curl: command not found`
```bash
# Solution: Install curl
apt-get install curl           # Debian/Ubuntu
yum install curl               # CentOS/RHEL
# OR use PowerShell Invoke-WebRequest
```

---

## Success Criteria

**RC-2 is LOCKED when:**
- ✅ Docker tests pass on Linux (9/9)
- ✅ Curl smoke test shows Retry-After header
- ✅ Problem Details JSON is valid
- ✅ No path leaks in instance field
- ✅ No middleware mangling of headers

**Sign-Off Checklist:**
- [ ] Docker test: 9 passed, 0 skipped, 0 failed
- [ ] Curl test: 429 with Retry-After header
- [ ] Instance format: `urn:decisionproof:trace:{uuid}`
- [ ] Content-Type: `application/problem+json`

---

## Next Steps

After verification:
1. Commit this guide to `/docs/RC2_VERIFICATION_GUIDE.md`
2. Update RC_ACCEPTANCE.md with verification results
3. Lock RC-2 gate
4. Proceed to RC-3 (if applicable)

---

**Document Version**: 1.0
**Last Updated**: 2026-02-15
**Author**: DPP Team + Claude Sonnet 4.5
