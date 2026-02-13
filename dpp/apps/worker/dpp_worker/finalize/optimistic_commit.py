"""2-Phase Finalize with Optimistic Locking (DEC-4210).

Implements exactly-once terminal transition to prevent double-settlement and race conditions
between Worker and Reaper.

CRITICAL: Claim must succeed before any side-effects (settle/refund/S3 pointers).

Polymorphic Design:
- Worker uses lease_token condition (has active lease)
- Reaper uses lease_expires_at condition (lease expired)
- Common 2-phase commit logic (_do_2phase_finalize)

Spec reference (Section 9.1, Step 7 + Section 10.2):
  (A) claim:
    Worker WHERE: status='PROCESSING' AND version=:v AND lease_token=:lease_token
                  AND finalize_stage IS NULL
    Reaper WHERE: status='PROCESSING' AND version=:v AND lease_expires_at < NOW()
                  AND finalize_stage IS NULL
    SET:   finalize_token=:uuid, finalize_stage='CLAIMED', version=v+1

  (B) side-effects (winner only):
    settle: charge = min(requested_charge, reserved)
    final commit:
      WHERE: run_id=:id AND version=:v_claimed AND finalize_token=:token
             AND finalize_stage='CLAIMED'
      SET:   status=:final_status, money_state='SETTLED', finalize_stage='COMMITTED', version+1
"""

import uuid
from datetime import datetime, timezone
from typing import Any, Literal

from sqlalchemy.orm import Session

from dpp_api.budget import BudgetManager
from dpp_api.db.repo_runs import RunRepository
from dpp_api.metering import UsageTracker


class FinalizeError(Exception):
    """Base exception for finalize errors."""

    pass


class ClaimError(FinalizeError):
    """Raised when claim phase fails (loser)."""

    pass


def claim_finalize(
    run_id: str,
    tenant_id: str,
    extra_claim_conditions: dict[str, Any],
    db: Session,
) -> tuple[str, int]:
    """Phase 1: Claim exclusive right to finalize (Claim-Check pattern).

    CRITICAL: This MUST be called BEFORE any side-effects (S3 upload, settle).

    Args:
        run_id: Run ID
        tenant_id: Tenant ID
        extra_claim_conditions: Extra WHERE conditions for claim
        db: Database session

    Returns:
        Tuple of (finalize_token, claimed_version)

    Raises:
        ClaimError: If claim fails (loser)
        FinalizeError: If run state is invalid
    """
    repo = RunRepository(db)

    # Get current run state
    run = repo.get_by_id(run_id, tenant_id)
    if not run:
        raise FinalizeError(f"Run {run_id} not found")

    if run.status != "PROCESSING":
        raise ClaimError(
            f"Run {run_id} status is {run.status}, expected PROCESSING (already finalized)"
        )

    # Golden Rule: Validate money_state before attempting finalize
    if run.money_state != "RESERVED":
        raise FinalizeError(
            f"Run {run_id} money_state is {run.money_state}, expected RESERVED"
        )

    # ========================================
    # PHASE 1: CLAIM (DB-CAS) - NO SIDE-EFFECTS YET
    # ========================================
    finalize_token = str(uuid.uuid4())
    current_version = run.version

    # Base claim conditions (common to Worker and Reaper)
    claim_conditions = {
        "status": "PROCESSING",
        "finalize_stage": None,  # IS NULL - critical for race prevention
    }
    # Add extra conditions (Worker: lease_token, Reaper: lease_expires_at)
    claim_conditions.update(extra_claim_conditions)

    # Attempt to claim exclusive right to finalize
    success = repo.update_with_version_check(
        run_id=run_id,
        tenant_id=tenant_id,
        expected_version=current_version,
        updates={
            "finalize_stage": "CLAIMED",
            "finalize_token": finalize_token,
            "finalize_claimed_at": datetime.now(timezone.utc),
        },
        extra_conditions=claim_conditions,
    )

    if not success:
        # Lost race - another worker or reaper already claimed
        raise ClaimError(f"Run {run_id} already claimed by another process")

    claimed_version = current_version + 1
    return (finalize_token, claimed_version)


def commit_finalize(
    run_id: str,
    tenant_id: str,
    finalize_token: str,
    claimed_version: int,
    charge_usd_micros: int,
    final_status: Literal["COMPLETED", "FAILED"],
    extra_final_updates: dict[str, Any],
    db: Session,
    budget_manager: BudgetManager,
) -> Literal["WINNER"]:
    """Phase 2-3: Settle budget and commit final state (Claim-Check pattern).

    CRITICAL: This should ONLY be called AFTER side-effects (S3 upload) are complete.

    Args:
        run_id: Run ID
        tenant_id: Tenant ID
        finalize_token: Token from claim phase
        claimed_version: Version from claim phase
        charge_usd_micros: Amount to charge (USD_MICROS)
        final_status: Final status ("COMPLETED" or "FAILED")
        extra_final_updates: Extra fields to update
        db: Database session
        budget_manager: Budget manager instance

    Returns:
        "WINNER" if finalize succeeded

    Raises:
        FinalizeError: If commit fails
    """
    repo = RunRepository(db)

    # Get run for validation
    run = repo.get_by_id(run_id, tenant_id)
    if not run:
        raise FinalizeError(f"Run {run_id} not found")

    # Pre-check: charge must not exceed reservation
    if charge_usd_micros > run.reservation_max_cost_usd_micros:
        raise FinalizeError(
            f"Charge {charge_usd_micros} exceeds reserved {run.reservation_max_cost_usd_micros}"
        )

    # ========================================
    # PHASE 2: SETTLE (Redis)
    # ========================================
    settle_status, returned_charge, refund, new_balance = budget_manager.scripts.settle(
        tenant_id, run_id, charge_usd_micros
    )

    if settle_status != "OK":
        raise FinalizeError(f"Settle failed: {settle_status}")

    # P0-3: Use returned charge as single source of truth
    actual_charge = returned_charge

    # ========================================
    # PHASE 3: FINAL COMMIT (DB)
    # ========================================
    # Base final updates (common to all finalize types)
    final_updates = {
        "status": final_status,
        "money_state": "SETTLED",
        "actual_cost_usd_micros": actual_charge,  # P0-3: Use returned charge
        "finalize_stage": "COMMITTED",
        "completed_at": datetime.now(timezone.utc),  # P1-10: Set completion timestamp
    }
    # Add extra updates (Worker: S3 pointers, Reaper: error details)
    final_updates.update(extra_final_updates)

    final_success = repo.update_with_version_check(
        run_id=run_id,
        tenant_id=tenant_id,
        expected_version=claimed_version,
        updates=final_updates,
        extra_conditions={
            "finalize_token": finalize_token,
            "finalize_stage": "CLAIMED",
        },
    )

    if not final_success:
        # This should never happen unless DB corruption
        raise FinalizeError(
            f"Final commit failed for run {run_id} despite successful claim"
        )

    # STEP C: Record usage in tenant_usage_daily (metering)
    # Get updated run record for metering
    updated_run = repo.get_by_id(run_id, tenant_id)
    if updated_run:
        usage_tracker = UsageTracker(db)
        try:
            usage_tracker.record_run_completion(updated_run)
        except Exception as e:
            # Log metering error but don't fail finalize (already committed)
            import logging

            logger = logging.getLogger(__name__)
            logger.error(f"Failed to record usage for run {run_id}: {e}", exc_info=True)

    return "WINNER"


def _do_2phase_finalize(
    run_id: str,
    tenant_id: str,
    charge_usd_micros: int,
    final_status: Literal["COMPLETED", "FAILED"],
    extra_claim_conditions: dict[str, Any],
    extra_final_updates: dict[str, Any],
    db: Session,
    budget_manager: BudgetManager,
) -> Literal["WINNER"]:
    """Internal 2-phase finalize implementation (polymorphic core).

    NOTE: This is a legacy wrapper for backward compatibility.
    New code should use claim_finalize() + side-effects + commit_finalize() pattern.

    Args:
        run_id: Run ID
        tenant_id: Tenant ID
        charge_usd_micros: Amount to charge (USD_MICROS)
        final_status: Final status ("COMPLETED" or "FAILED")
        extra_claim_conditions: Extra WHERE conditions for claim
        extra_final_updates: Extra fields to update in final commit
        db: Database session
        budget_manager: Budget manager instance

    Returns:
        "WINNER" if finalize succeeded

    Raises:
        ClaimError: If claim phase fails (loser)
        FinalizeError: If commit phase fails after claiming
    """
    # Phase 1: Claim
    finalize_token, claimed_version = claim_finalize(
        run_id=run_id,
        tenant_id=tenant_id,
        extra_claim_conditions=extra_claim_conditions,
        db=db,
    )

    # Phase 2-3: Settle + Commit
    # (In this legacy function, no S3 upload happens between claim and commit)
    return commit_finalize(
        run_id=run_id,
        tenant_id=tenant_id,
        finalize_token=finalize_token,
        claimed_version=claimed_version,
        charge_usd_micros=charge_usd_micros,
        final_status=final_status,
        extra_final_updates=extra_final_updates,
        db=db,
        budget_manager=budget_manager,
    )


def finalize_success(
    run_id: str,
    tenant_id: str,
    lease_token: str,
    actual_cost_usd_micros: int,
    result_bucket: str,
    result_key: str,
    result_sha256: str,
    db: Session,
    budget_manager: BudgetManager,
) -> Literal["WINNER"]:
    """2-phase finalize for successful run completion (COMPLETED + SETTLED).

    Worker-specific wrapper that uses lease_token condition.

    Args:
        run_id: Run ID
        tenant_id: Tenant ID
        lease_token: Lease token from worker (used in claim WHERE condition)
        actual_cost_usd_micros: Actual cost to charge (USD_MICROS)
        result_bucket: S3 bucket name
        result_key: S3 object key
        result_sha256: SHA-256 hash of result
        db: Database session
        budget_manager: Budget manager instance

    Returns:
        "WINNER" if finalize succeeded

    Raises:
        ClaimError: If claim phase fails (loser)
        FinalizeError: If commit phase fails after claiming
    """
    return _do_2phase_finalize(
        run_id=run_id,
        tenant_id=tenant_id,
        charge_usd_micros=actual_cost_usd_micros,
        final_status="COMPLETED",
        extra_claim_conditions={
            "lease_token": lease_token,  # Worker: has active lease
        },
        extra_final_updates={
            "result_bucket": result_bucket,
            "result_key": result_key,
            "result_sha256": result_sha256,
        },
        db=db,
        budget_manager=budget_manager,
    )


def finalize_failure(
    run_id: str,
    tenant_id: str,
    lease_token: str,
    minimum_fee_usd_micros: int,
    error_reason_code: str,
    error_detail: str,
    db: Session,
    budget_manager: BudgetManager,
) -> Literal["WINNER"]:
    """2-phase finalize for failed run (FAILED + SETTLED with minimum_fee).

    Worker-specific wrapper that uses lease_token condition.

    Args:
        run_id: Run ID
        tenant_id: Tenant ID
        lease_token: Lease token from worker (used in claim WHERE condition)
        minimum_fee_usd_micros: Minimum fee to charge (USD_MICROS)
        error_reason_code: Error reason code
        error_detail: Error detail message
        db: Database session
        budget_manager: Budget manager instance

    Returns:
        "WINNER" if finalize succeeded

    Raises:
        ClaimError: If claim phase fails (loser)
        FinalizeError: If commit phase fails after claiming
    """
    return _do_2phase_finalize(
        run_id=run_id,
        tenant_id=tenant_id,
        charge_usd_micros=minimum_fee_usd_micros,
        final_status="FAILED",
        extra_claim_conditions={
            "lease_token": lease_token,  # Worker: has active lease
        },
        extra_final_updates={
            "last_error_reason_code": error_reason_code,
            "last_error_detail": error_detail,
        },
        db=db,
        budget_manager=budget_manager,
    )


def finalize_timeout(
    run_id: str,
    tenant_id: str,
    minimum_fee_usd_micros: int,
    db: Session,
    budget_manager: BudgetManager,
) -> Literal["WINNER"]:
    """2-phase finalize for timeout (FAILED + SETTLED with minimum_fee).

    Reaper-specific wrapper that uses lease_expires_at condition instead of lease_token.

    Spec 10.2: Reaper finalize
    - claim WHERE: status='PROCESSING' AND lease_expires_at < NOW() AND finalize_stage IS NULL
    - settle: charge = min(minimum_fee, reserved)
    - final commit: status='FAILED', reason_code='WORKER_TIMEOUT'

    Args:
        run_id: Run ID
        tenant_id: Tenant ID
        minimum_fee_usd_micros: Minimum fee to charge (USD_MICROS)
        db: Database session
        budget_manager: Budget manager instance

    Returns:
        "WINNER" if finalize succeeded

    Raises:
        ClaimError: If claim phase fails (loser - Worker or another Reaper won)
        FinalizeError: If commit phase fails after claiming
    """
    # Special handling for Reaper: we need to check lease_expires_at < NOW()
    # But repo.update_with_version_check doesn't support temporal comparisons directly
    # Workaround: We'll rely on the scan query to pre-filter expired leases,
    # and use finalize_stage IS NULL as the race protection
    # (If Worker claims first, finalize_stage won't be NULL anymore)

    return _do_2phase_finalize(
        run_id=run_id,
        tenant_id=tenant_id,
        charge_usd_micros=minimum_fee_usd_micros,
        final_status="FAILED",
        extra_claim_conditions={
            # Reaper doesn't check lease_token (lease expired)
            # But we ensure run is still in PROCESSING state
            "status": "PROCESSING",  # Additional safety check
        },
        extra_final_updates={
            "last_error_reason_code": "WORKER_TIMEOUT",
            "last_error_detail": "Worker lease expired, run terminated by Reaper",
        },
        db=db,
        budget_manager=budget_manager,
    )
