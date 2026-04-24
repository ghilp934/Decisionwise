# Decisionproof v0.4 Release Notes

> ⚠️ **LEGACY / SUPERSEDED (2026-04-24, MT0A-1 Surface Sync Patch)**
>
> This file is retained for historical reference only. Several statements below — including the `dpp_live_{key}` auth format, the "1,000 decision credits / hard cap 2,000" usage model, and the "No TTL" retention phrasing — have been **explicitly superseded** by the MT0A-1 DEC register (`_DP_v1_0/open_ssot_decisions_v0.2_redteam.md`). Do **not** rely on this document for current API, auth, pricing, retention, or support contract. For the authoritative current state, see:
>
> - Quickstart (current API): `/docs/quickstart.html`
> - Sandbox pricing: `/pricing.html`
> - Terms & retention: `/terms.html`
> - SSOT: `dpp/docs/SPEC_LOCK_PUBLIC_CONTRACT.md` (MT0A-1 aligned)
> - LLM-readable summary: `/llms.txt`, `/llms-full.txt`
>
> Per `/llms.txt`, this file is listed among retired surfaces.

> **Status**: Paid private beta — not generally available.
> This document covers the v0.4 release candidate for invited beta participants.

## Highlights

Decisionproof v0.4 introduces the execution governance layer for AI decisions:
spend caps, receipts, and deterministic run-lifecycle recovery for AI workloads.

Key capabilities landing in v0.4:
- `POST /v1/runs` with idempotent state machine, lease-based workers, and staged finalize
- Per-run cost cap (`max_cost_usd`) with budget reservation before work starts
- WORM-protected audit evidence storage (write-once, read-many S3)
- IETF-standard RateLimit headers on all `/v1/*` responses
- Tenant-isolated API key authentication (`Authorization: Bearer dpp_live_{key}`)
- PayPal-only payment processing — no card credentials stored by the service

## Changes

### API

- Base URL: `https://api.decisionproof.io.kr`
- Authentication: `Authorization: Bearer dpp_live_{key}` (up to 3 keys per workspace)
- `Idempotency-Key` header required on `POST /v1/runs`
- Async run pattern: `POST /v1/runs` → 202 Accepted + `run_id`; poll `GET /v1/runs/{run_id}`
- Error format: RFC 9457 Problem Details (`application/problem+json`)
- Canonical body keys: `pack_type`, `inputs`, `max_cost_usd`

### Infrastructure

- AWS EKS (Kubernetes), RDS (PostgreSQL), ElastiCache (Redis), S3 (WORM audit storage)
- Reaper reconciliation loop for deterministic recovery from worker crashes and timeouts

### Billing

- US$29 per 30-day access cycle, PayPal only, no auto-renewal
- 1,000 decision credits included per cycle; hard cap 2,000 per cycle
- Per-run cost cap: US$5.00

## Known Issues

- `on_event` deprecation warning from FastAPI startup handler — cosmetic only; lifespan migration tracked for v0.5
- No uptime SLA published during paid private beta period
- APIs, limits, and operational defaults may change on reasonable notice during beta

## Rollback Plan

If a critical defect is identified post-release:
1. Operator revokes affected API keys from the dashboard
2. In-flight runs are allowed to complete or time out through the reaper loop
3. A patch release is cut and communicated to beta participants by email
4. Access is restored once the patch gates pass

## Compatibility

This is the initial public release of the v0.4 API surface. No prior stable API version exists for migration compatibility purposes.

Breaking changes between RC builds and the GA surface will be communicated to beta participants in advance.
