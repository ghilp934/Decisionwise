# DecisionProof API Platform - Release Notes v0.4.0-rc1

**Version**: v0.4.0-rc1
**Commit**: `86d2854`
**Release Date**: 2026-02-15 (KST)
**Status**: Release Candidate - Pilot Ready

---

## Summary

Version 0.4.0-rc1 represents a major quality and observability milestone, with 7 release contract (RC) gates verified and 100% test pass rate achieved. This release establishes production-grade billing accuracy, error handling, and distributed tracing capabilities.

**Key Achievement**: All RC-1 through RC-7 contract gates PASSED ✅

---

## Highlights

### ✅ Billing Accuracy & Traceability (RC-1)
- Idempotent metering with PostgreSQL constraints
- S3 metadata-based cost traceability
- Zero money leak verified through chaos testing

### ✅ RFC 9457 Error Handling (RC-2)
- Standardized problem detail responses across all error paths
- Consistent `application/problem+json` media type
- Client-friendly error messages with troubleshooting guidance

### ✅ IETF RateLimit Headers (RC-3)
- Standards-compliant rate limit headers (`RateLimit-Policy`, `RateLimit`, `Retry-After`)
- Client-friendly quota visibility
- Atomic rate limit enforcement (no race conditions)

### ✅ Billing Invariants (RC-4)
- Budget isolation per tenant (Redis-backed)
- Atomic reserve-then-settle pattern
- Reconciliation loops for audit integrity

### ✅ Production Documentation (RC-5)
- Comprehensive deployment guide
- Incident response runbooks
- Architecture decision records

### ✅ Security Hardening (RC-6)
- Thread-safe session management
- AWS credential security (IAM roles only)
- Explicit IntegrityError handling
- Concurrent safety verified (20-thread stress tests)

### ✅ OpenTelemetry Integration (RC-7)
- Distributed tracing with W3C Trace Context
- HTTP request duration metrics
- Log correlation (trace_id/span_id injection)

---

## Changes

### API Enhancements
- **POST /v1/runs**: Idempotency-Key support with PostgreSQL constraint enforcement
- **Error Responses**: All error paths now return RFC 9457 Problem Details
- **Rate Limiting**: IETF-compliant headers on all /v1/* endpoints
- **Health Endpoints**: `/health` and `/readyz` for monitoring

### Worker Improvements
- Thread-safe heartbeat mechanism (session factory pattern)
- Graceful shutdown with in-flight request completion
- S3 metadata enrichment for cost attribution

### Observability
- Structured JSON logging with trace context
- OpenTelemetry span export for distributed tracing
- HTTP server request duration metrics (histogram)

### Testing
- **133 tests** passing (100% success rate)
- **48% code coverage** across critical paths
- Chaos testing for money leak scenarios
- Concurrent safety verification

---

## Known Issues

### Limitations
- **Windows Static Export**: `output: 'export'` mode encounters EISDIR errors on Windows environments (deferred to future milestone)
- **LocalStack Dependency**: Integration tests require LocalStack for AWS service mocking

### Workarounds
- Use `npm run dev` for development on Windows
- Ensure LocalStack is running before executing integration tests

---

## Compatibility

### Breaking Changes
None. This is a feature-additive release.

### API Compatibility
- All existing API endpoints remain unchanged
- New headers added (`RateLimit-Policy`, `RateLimit`) are backwards-compatible
- Error response structure enhanced (still valid JSON, media type changed to `application/problem+json`)

### Database Migrations
- Alembic migrations required (see deployment guide)
- Idempotent - safe to run multiple times

### Environment Variables
New optional variables:
- `OTEL_SEMCONV_STABILITY_OPT_IN=http` - Enable stable HTTP semantic conventions (recommended)
- `LOG_LEVEL` - Set logging verbosity (default: INFO)

---

## Rollback Plan

### Application Rollback
```bash
# Kubernetes example
kubectl rollout undo deployment/dpp-api
kubectl rollout undo deployment/dpp-worker
kubectl rollout undo deployment/dpp-reaper

# Verify rollback
kubectl rollout status deployment/dpp-api
```

### Database Rollback
```bash
# If database migration fails
python -m alembic downgrade -1

# Verify rollback
python -m alembic current
```

### Rollback Decision Criteria
Trigger rollback if:
- Critical alerts > 3 in first hour
- Test coverage drops below 90%
- Money leak incidents detected (AUDIT_REQUIRED logs)
- Database migration fails

**Expected Rollback Time**: < 5 minutes for application, < 10 minutes with database migration

---

## Deployment Checklist

### Pre-Deployment
- [ ] Run full test suite: `python -m pytest -v` (expect 133 passed)
- [ ] Verify database migration: `python -m alembic check`
- [ ] Review environment variables (no hardcoded credentials)
- [ ] Confirm staging smoke test passed

### Post-Deployment
- [ ] Verify health endpoints: `/health` and `/readyz` return 200
- [ ] Check logs for trace_id visibility
- [ ] Monitor for CRITICAL alerts (first 1 hour)
- [ ] Execute smoke test E2E run

---

## Testing Summary

### Contract Gate Status
- **RC-1** (Billing Accuracy): ✅ PASSED
- **RC-2** (RFC 9457 Errors): ✅ PASSED
- **RC-3** (IETF RateLimit): ✅ PASSED
- **RC-4** (Billing Invariants): ✅ PASSED
- **RC-5** (Documentation): ✅ PASSED
- **RC-6** (Security Hardening): ✅ PASSED
- **RC-7** (OpenTelemetry): ✅ PASSED

### Test Metrics
- **Total Tests**: 137 (133 passed, 4 skipped)
- **Success Rate**: 100%
- **Code Coverage**: 48% (critical paths covered)
- **Chaos Tests**: 5/5 money leak scenarios passed

---

## Upgrade Guide

### From Previous Versions
1. **Database Migration**: Run `python -m alembic upgrade head`
2. **Environment Variables**: Add optional `OTEL_SEMCONV_STABILITY_OPT_IN=http`
3. **Deployment**: Follow blue-green deployment pattern
4. **Verification**: Check `/readyz` endpoint for service health

### First-Time Deployment
Refer to deployment guide in repository for detailed infrastructure setup instructions.

---

## Next Steps

### Upcoming in v0.4.1
- Additional observability dashboards
- Enhanced error recovery mechanisms
- Performance optimizations

### Feedback
Report issues or provide feedback through your designated support channel.

---

**Release Prepared By**: Automated Release System
**Approval Status**: Pending Pilot Validation
**Documentation**: See PILOT_READY.md for pilot testing criteria
