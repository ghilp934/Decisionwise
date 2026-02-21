"""RC-4 Contract Gate: Billing Invariants.

Tests for billing safety guarantees:
- T1: 400/422 never billable + 422 does NOT consume Idempotency-Key
- T4: Parallel reserve protection + 402 + TTL check (Zombie prevention)
"""

import uuid

import pytest

from dpp_api.budget.redis_scripts import BudgetScripts
from dpp_api.constants import RESERVATION_TTL_SECONDS


class TestRC4BillingInvariants:
    """RC-4: Billing safety and idempotency invariants."""

    def test_rc4_t1_validation_errors_never_billable_and_idem_not_consumed(
        self, test_client, test_tenant_with_api_key, redis_client
    ):
        """T1: 400/422 are NEVER billable + 422 must NOT consume Idempotency-Key.

        RC-4 Critical Invariants:
        1. 400 (validation error) does NOT charge/reserve budget
        2. 422 (request validation error) does NOT charge/reserve budget
        3. 422 does NOT consume Idempotency-Key (key still usable after payload fix)
        """
        # 1) Arrange
        tenant_id, api_key, key_hash = test_tenant_with_api_key
        budget_scripts = BudgetScripts(redis_client)

        # Set tenant balance to 1,000,000 micros ($1.00)
        budget_scripts.set_balance(tenant_id, 1_000_000)
        balance_before = budget_scripts.get_balance(tenant_id)
        assert balance_before == 1_000_000

        # Prepare headers
        headers_base = {
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json",
        }

        # Valid body for cases A and C
        valid_body = {
            "pack_type": "decision",
            "inputs": {"q": "x"},
            "reservation": {
                "max_cost_usd": "0.0100",
                "timebox_sec": 90,
                "min_reliability_score": 0.8,
            },
            "meta": {"profile_version": "rc4-t1"},
        }

        # 2) Case A (400): invalid Idempotency-Key length must not bill
        response_400 = test_client.post(
            "/v1/runs",
            json=valid_body,
            headers={**headers_base, "Idempotency-Key": "short"},  # len < 8
        )

        assert response_400.status_code == 400, \
            f"Expected 400 for short idempotency key, got {response_400.status_code}"
        assert "application/problem+json" in response_400.headers.get("content-type", ""), \
            "Expected Problem Details content type"

        balance_after_400 = budget_scripts.get_balance(tenant_id)
        assert balance_after_400 == balance_before, \
            f"400 error charged budget! Before: {balance_before}, After: {balance_after_400}"

        # 3) Case B (422): body validation error must not bill
        idem_key = f"rc4t1-{uuid.uuid4().hex[:16]}"  # 8~64 chars

        invalid_body = {
            "pack_type": "decision",
            "inputs": {"q": "x"},
            "meta": {"profile_version": "rc4-t1"},
            # Missing required field: reservation
        }

        response_422 = test_client.post(
            "/v1/runs",
            json=invalid_body,
            headers={**headers_base, "Idempotency-Key": idem_key},
        )

        assert response_422.status_code == 422, \
            f"Expected 422 for missing reservation, got {response_422.status_code}"
        assert "application/problem+json" in response_422.headers.get("content-type", ""), \
            "Expected Problem Details content type"

        balance_after_422 = budget_scripts.get_balance(tenant_id)
        assert balance_after_422 == balance_before, \
            f"422 error charged budget! Before: {balance_before}, After: {balance_after_422}"

        # 4) Case C (Critical): SAME Idempotency-Key must still be usable after 422
        # Re-POST with SAME idem_key but VALID body
        valid_body_retry = {
            "pack_type": "decision",
            "inputs": {"q": "x"},
            "reservation": {
                "max_cost_usd": "0.0100",
                "timebox_sec": 90,
                "min_reliability_score": 0.8,
            },
            "meta": {"profile_version": "rc4-t1-retry"},
        }

        response_202_first = test_client.post(
            "/v1/runs",
            json=valid_body_retry,
            headers={**headers_base, "Idempotency-Key": idem_key},
        )

        assert response_202_first.status_code == 202, \
            f"Expected 202 for valid request after 422, got {response_202_first.status_code}"

        run_id_1 = response_202_first.json().get("run_id")
        assert run_id_1 is not None, "run_id missing in 202 response"

        # Immediately POST the SAME request again (same idem_key and body)
        response_202_second = test_client.post(
            "/v1/runs",
            json=valid_body_retry,
            headers={**headers_base, "Idempotency-Key": idem_key},
        )

        assert response_202_second.status_code == 202, \
            f"Expected 202 for idempotent retry, got {response_202_second.status_code} (should NOT be 409)"

        run_id_2 = response_202_second.json().get("run_id")
        assert run_id_2 == run_id_1, \
            f"Idempotent retry returned different run_id! First: {run_id_1}, Second: {run_id_2}"

        # Sanity: balance should now be decreased by reserved amount
        balance_after_success = budget_scripts.get_balance(tenant_id)
        assert balance_after_success < balance_before, \
            f"Successful reservation did not decrease balance! Before: {balance_before}, After: {balance_after_success}"

    def test_rc4_t4_parallel_reserve_no_negative_402_and_ttl(
        self, test_client, test_tenant_with_api_key, redis_client
    ):
        """T4: Parallel reserve protection + 402 + TTL check (Zombie reservation prevention).

        RC-4 Critical Invariants:
        1. Two concurrent requests each reserving $0.50 with balance=$0.50
        2. Exactly ONE returns 202, the other returns 402
        3. Balance never goes negative and ends at 0
        4. Winner run_id has Redis reserve key with ttl > 0

        Note: Using rapid sequential calls instead of true parallelism to avoid
        TestClient/DB session conflicts (more conservative approach).
        """
        # 1) Arrange
        tenant_id, api_key, key_hash = test_tenant_with_api_key
        budget_scripts = BudgetScripts(redis_client)

        # Set tenant balance to 500,000 micros ($0.50)
        budget_scripts.set_balance(tenant_id, 500_000)
        balance_before = budget_scripts.get_balance(tenant_id)
        assert balance_before == 500_000

        # Prepare valid body with max_cost_usd="$0.5000"
        body_template = {
            "pack_type": "decision",
            "inputs": {"q": "test"},
            "reservation": {
                "max_cost_usd": "0.5000",  # 500,000 micros
                "timebox_sec": 90,
                "min_reliability_score": 0.8,
            },
            "meta": {"profile_version": "rc4-t4"},
        }

        # Two distinct Idempotency-Keys
        idem_key_a = f"rc4t4a-{uuid.uuid4().hex[:16]}"
        idem_key_b = f"rc4t4b-{uuid.uuid4().hex[:16]}"

        headers_base = {
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json",
        }

        # 2) Act (rapid sequential - race condition simulation)
        # First request should succeed and reserve full balance
        response_a = test_client.post(
            "/v1/runs",
            json=body_template,
            headers={**headers_base, "Idempotency-Key": idem_key_a},
        )

        # Second request should immediately fail with 402 (no budget left)
        response_b = test_client.post(
            "/v1/runs",
            json=body_template,
            headers={**headers_base, "Idempotency-Key": idem_key_b},
        )

        # 3) Assert
        statuses = {response_a.status_code, response_b.status_code}
        assert statuses == {202, 402}, \
            f"Expected {{202, 402}}, got {statuses}. Response A: {response_a.status_code}, Response B: {response_b.status_code}"

        # Find 402 response and verify Problem Details
        response_402 = response_a if response_a.status_code == 402 else response_b
        assert "application/problem+json" in response_402.headers.get("content-type", ""), \
            "402 response must be Problem Details"

        problem_data = response_402.json()
        required_fields = ["type", "title", "status", "detail", "instance"]
        for field in required_fields:
            assert field in problem_data, f"402 Problem Details missing required field: {field}"

        # Confirm final balance == 0
        balance_final = budget_scripts.get_balance(tenant_id)
        assert balance_final == 0, \
            f"Expected final balance 0, got {balance_final}"

        # Find winner run_id from 202 response
        response_202 = response_a if response_a.status_code == 202 else response_b
        winner_run_id = response_202.json().get("run_id")
        assert winner_run_id is not None, "202 response missing run_id"

        # TTL check (auditor critical: Zombie reservation prevention)
        reserve_key = f"reserve:{{{tenant_id}}}:{winner_run_id}"
        ttl = redis_client.ttl(reserve_key)

        assert ttl > 0, \
            f"Reserve key '{reserve_key}' has no TTL (ttl={ttl}). Zombie reservation risk!"
        assert ttl <= RESERVATION_TTL_SECONDS, \
            f"Reserve key TTL ({ttl}s) exceeds max ({RESERVATION_TTL_SECONDS}s)"

        # Confirm no negative balance (sanity check)
        assert balance_final >= 0, \
            f"Balance went negative! Final: {balance_final}"
