"""Retention Cleanup Loop (P0-6).

Periodically scans for expired run results and deletes S3 objects.

Retention Policy:
- Completed runs older than DPP_RETENTION_DAYS (default: 30) are eligible for cleanup
- S3 result objects are deleted
- DB records updated with result_cleared_at timestamp
- DB run rows are NOT deleted (audit trail preservation)
"""

import logging
import os
import time
from typing import Optional

from sqlalchemy.orm import Session

from dpp_api.db.repo_runs import RunRepository
from dpp_api.storage.s3_client import S3Client

logger = logging.getLogger(__name__)


def get_retention_days() -> int:
    """Get retention period in days from environment.

    Returns:
        Retention days (default: 30)
    """
    return int(os.getenv("DPP_RETENTION_DAYS", "30"))


def get_retention_loop_interval_seconds() -> int:
    """Get retention loop interval in seconds.

    Returns:
        Interval seconds (default: 86400 = 24 hours)
    """
    return int(os.getenv("DPP_RETENTION_LOOP_INTERVAL_SECONDS", "86400"))


def run_retention_cleanup(
    session: Session,
    s3_client: S3Client,
    cutoff_days: int,
    batch_size: int = 100,
) -> int:
    """Run one iteration of retention cleanup.

    Args:
        session: Database session
        s3_client: S3 client instance
        cutoff_days: Number of days after completion to consider expired
        batch_size: Maximum number of runs to process per iteration

    Returns:
        Number of S3 objects deleted
    """
    repo = RunRepository(session)

    # Find expired runs
    expired_runs = repo.find_expired_runs(cutoff_days=cutoff_days, limit=batch_size)

    if not expired_runs:
        logger.info("No expired runs found for retention cleanup")
        return 0

    logger.info(f"Found {len(expired_runs)} expired runs for retention cleanup")

    # Delete S3 objects and track successes
    deleted_count = 0
    successfully_cleared_run_ids = []

    for run in expired_runs:
        if not run.result_s3_key or not run.result_s3_bucket:
            logger.warning(f"Run {run.run_id} missing S3 info, skipping")
            continue

        try:
            # Delete S3 object
            s3_client.delete_object(
                bucket=run.result_s3_bucket,
                key=run.result_s3_key,
            )
            deleted_count += 1
            successfully_cleared_run_ids.append(run.run_id)

        except Exception as e:
            logger.error(
                f"Failed to delete S3 object for run {run.run_id}: {e}",
                exc_info=True,
            )
            # Continue with other runs (don't fail entire batch)

    # Mark runs as cleared in DB
    if successfully_cleared_run_ids:
        repo.mark_results_cleared(successfully_cleared_run_ids)
        logger.info(
            f"Retention cleanup completed: {deleted_count} S3 objects deleted, "
            f"{len(successfully_cleared_run_ids)} runs marked as cleared"
        )

    return deleted_count


def retention_loop(
    session_factory,
    s3_client: Optional[S3Client] = None,
    interval_seconds: Optional[int] = None,
    cutoff_days: Optional[int] = None,
):
    """Retention cleanup loop (runs in background thread).

    Args:
        session_factory: SQLAlchemy sessionmaker
        s3_client: S3 client instance (default: create new instance)
        interval_seconds: Loop interval in seconds (default: from env DPP_RETENTION_LOOP_INTERVAL_SECONDS)
        cutoff_days: Retention cutoff days (default: from env DPP_RETENTION_DAYS)
    """
    # Initialize parameters
    if s3_client is None:
        from dpp_api.storage.s3_client import get_s3_client
        s3_client = get_s3_client()

    if interval_seconds is None:
        interval_seconds = get_retention_loop_interval_seconds()

    if cutoff_days is None:
        cutoff_days = get_retention_days()

    logger.info(
        f"Starting retention cleanup loop: interval={interval_seconds}s, cutoff={cutoff_days} days"
    )

    while True:
        try:
            with session_factory() as session:
                deleted_count = run_retention_cleanup(
                    session=session,
                    s3_client=s3_client,
                    cutoff_days=cutoff_days,
                )

                if deleted_count > 0:
                    logger.info(f"Retention cleanup deleted {deleted_count} S3 objects")

        except Exception as e:
            logger.error(f"Retention cleanup loop error: {e}", exc_info=True)

        # Sleep until next iteration
        time.sleep(interval_seconds)
