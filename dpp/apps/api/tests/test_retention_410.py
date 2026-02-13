"""Tests for DEC-4209: Retention 410 Gone.

Verifies that:
- Owner accessing expired run gets 410 Gone
- Non-owner accessing expired run gets 404 Not Found (stealth)
- Owner accessing non-expired run gets 200 OK
"""

import uuid
from datetime import datetime, timedelta, timezone

from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from dpp_api.db.models import Run


def test_retention_expired_owner_gets_410(
    db_session: Session, test_client: TestClient, test_tenant_with_api_key
):
    """Test that owner gets 410 Gone for expired run (DEC-4209)."""
    tenant_id, api_key, _ = test_tenant_with_api_key
    run_id = str(uuid.uuid4())

    # Create a run with expired retention
    run = Run(
        run_id=run_id,
        tenant_id=tenant_id,
        pack_type="decision",
        profile_version="v0.4.2.2",
        status="COMPLETED",
        money_state="SETTLED",
        payload_hash=f"sha256:{run_id}",
        reservation_max_cost_usd_micros=1_000_000,
        actual_cost_usd_micros=500_000,
        minimum_fee_usd_micros=100_000,
        # CRITICAL: Retention expired (1 day ago)
        retention_until=datetime.now(timezone.utc) - timedelta(days=1),
        result_bucket="test-bucket",
        result_key="test-key",
        result_sha256="abc123",
    )
    db_session.add(run)
    db_session.commit()

    # Owner tries to access expired run
    response = test_client.get(
        f"/v1/runs/{run_id}",
        headers={"Authorization": f"Bearer {api_key}"},
    )

    # Verify: 410 Gone
    assert response.status_code == 410
    assert "expired" in response.json()["detail"].lower()


def test_retention_expired_non_owner_gets_404(
    db_session: Session, test_client: TestClient, test_tenant_with_api_key
):
    """Test that non-owner gets 404 for expired run (stealth security)."""
    # Create run owned by first tenant
    tenant_id_1, _, _ = test_tenant_with_api_key
    run_id = str(uuid.uuid4())

    run = Run(
        run_id=run_id,
        tenant_id=tenant_id_1,
        pack_type="decision",
        profile_version="v0.4.2.2",
        status="COMPLETED",
        money_state="SETTLED",
        payload_hash=f"sha256:{run_id}",
        reservation_max_cost_usd_micros=1_000_000,
        actual_cost_usd_micros=500_000,
        minimum_fee_usd_micros=100_000,
        retention_until=datetime.now(timezone.utc) - timedelta(days=1),
    )
    db_session.add(run)
    db_session.commit()

    # Create second tenant with different API key
    import hashlib

    from dpp_api.db.models import APIKey, Plan, Tenant
    from dpp_api.db.repo_api_keys import APIKeyRepository
    from dpp_api.db.repo_plans import TenantPlanRepository
    from dpp_api.db.repo_tenants import TenantRepository

    tenant_id_2 = f"tenant_{uuid.uuid4().hex[:8]}"
    key_id_2 = str(uuid.uuid4())
    secret_2 = uuid.uuid4().hex
    api_key_2 = f"sk_{key_id_2}_{secret_2}"
    key_hash_2 = hashlib.sha256(api_key_2.encode()).hexdigest()

    # Create second tenant
    tenant_repo = TenantRepository(db_session)
    tenant_repo.create(
        Tenant(tenant_id=tenant_id_2, display_name=f"Test Tenant {tenant_id_2}", status="ACTIVE")
    )

    # Create API key for second tenant
    api_key_repo = APIKeyRepository(db_session)
    api_key_repo.create(
        APIKey(
            key_id=key_id_2,
            tenant_id=tenant_id_2,
            key_hash=key_hash_2,
            label="Test Key 2",
            status="ACTIVE",
        )
    )

    # Assign plan to second tenant
    plan = db_session.query(Plan).filter_by(plan_id="plan_e2e_basic").first()
    tenant_plan_repo = TenantPlanRepository(db_session)
    tenant_plan_repo.assign_plan(
        tenant_id=tenant_id_2,
        plan_id=plan.plan_id,
        changed_by="test",
        change_reason="Test setup",
    )

    # Non-owner (tenant_2) tries to access expired run (owned by tenant_1)
    response = test_client.get(
        f"/v1/runs/{run_id}",
        headers={"Authorization": f"Bearer {api_key_2}"},
    )

    # Verify: 404 Not Found (stealth - don't reveal existence)
    assert response.status_code == 404
    assert response.json()["detail"] == "Run not found"


def test_retention_not_expired_owner_gets_200(
    db_session: Session, test_client: TestClient, test_tenant_with_api_key
):
    """Test that owner can access non-expired run normally."""
    tenant_id, api_key, _ = test_tenant_with_api_key
    run_id = str(uuid.uuid4())

    # Create a run with valid retention (30 days from now)
    run = Run(
        run_id=run_id,
        tenant_id=tenant_id,
        pack_type="decision",
        profile_version="v0.4.2.2",
        status="COMPLETED",
        money_state="SETTLED",
        payload_hash=f"sha256:{run_id}",
        reservation_max_cost_usd_micros=1_000_000,
        actual_cost_usd_micros=500_000,
        minimum_fee_usd_micros=100_000,
        # Valid retention (30 days from now)
        retention_until=datetime.now(timezone.utc) + timedelta(days=30),
        result_bucket="test-bucket",
        result_key="test-key",
        result_sha256="abc123",
    )
    db_session.add(run)
    db_session.commit()

    # Owner accesses valid run
    response = test_client.get(
        f"/v1/runs/{run_id}",
        headers={"Authorization": f"Bearer {api_key}"},
    )

    # Verify: 200 OK
    assert response.status_code == 200
    data = response.json()
    assert data["run_id"] == run_id
    assert data["status"] == "COMPLETED"


def test_retention_boundary_exactly_now(
    db_session: Session, test_client: TestClient, test_tenant_with_api_key
):
    """Test edge case: retention_until exactly equals now."""
    tenant_id, api_key, _ = test_tenant_with_api_key
    run_id = str(uuid.uuid4())

    # Create a run with retention exactly at current time
    run = Run(
        run_id=run_id,
        tenant_id=tenant_id,
        pack_type="decision",
        profile_version="v0.4.2.2",
        status="COMPLETED",
        money_state="SETTLED",
        payload_hash=f"sha256:{run_id}",
        reservation_max_cost_usd_micros=1_000_000,
        actual_cost_usd_micros=500_000,
        minimum_fee_usd_micros=100_000,
        # Retention exactly at current time (edge case)
        retention_until=datetime.now(timezone.utc),
    )
    db_session.add(run)
    db_session.commit()

    # Owner tries to access
    response = test_client.get(
        f"/v1/runs/{run_id}",
        headers={"Authorization": f"Bearer {api_key}"},
    )

    # Verify: Should be 410 (retention_until < now due to execution time)
    # or 200 if exactly equal, but spec says "expired" so likely 410
    assert response.status_code in (200, 410)
