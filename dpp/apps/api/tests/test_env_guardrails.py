"""
T1/T2/T3: Environment variable guardrail tests.

Ops Hardening v2: Verify S3Client and SQSClient fail-fast on missing env vars.
T3: Supabase production guardrails (P0-1, P0-2, P0-3, P0-4).
"""

import os
from unittest.mock import MagicMock, patch

import pytest

from dpp_api.db.engine import _validate_supabase_production_config


def test_s3_client_no_env_raises_valueerror():
    """
    T1-A: S3Client MUST raise ValueError when neither S3_RESULT_BUCKET nor DPP_RESULTS_BUCKET set.

    Ops Hardening v2: No silent "dpp-results" default.
    """
    # Clear all bucket env vars
    env = {}

    with patch.dict("os.environ", env, clear=True):
        from dpp_api.storage.s3_client import S3Client

        with pytest.raises(ValueError, match="S3_RESULT_BUCKET"):
            S3Client()


def test_s3_client_uses_s3_result_bucket():
    """
    T1-B: S3Client MUST use S3_RESULT_BUCKET when set (canonical env var).
    """
    env = {"S3_RESULT_BUCKET": "my-production-bucket"}

    with patch.dict("os.environ", env, clear=True):
        from dpp_api.storage.s3_client import S3Client

        client = S3Client()
        assert client.bucket == "my-production-bucket"


def test_s3_client_fallback_to_dpp_results_bucket():
    """
    T1-C: S3Client MUST fall back to DPP_RESULTS_BUCKET (backward compatibility).
    """
    env = {"DPP_RESULTS_BUCKET": "legacy-bucket-name"}

    with patch.dict("os.environ", env, clear=True):
        from dpp_api.storage.s3_client import S3Client

        client = S3Client()
        assert client.bucket == "legacy-bucket-name"


def test_s3_client_prefers_canonical_over_legacy():
    """
    T1-D: S3Client MUST prefer S3_RESULT_BUCKET over DPP_RESULTS_BUCKET.
    """
    env = {
        "S3_RESULT_BUCKET": "canonical-bucket",
        "DPP_RESULTS_BUCKET": "legacy-bucket",
    }

    with patch.dict("os.environ", env, clear=True):
        from dpp_api.storage.s3_client import S3Client

        client = S3Client()
        assert client.bucket == "canonical-bucket"


def test_sqs_client_no_queue_url_raises_valueerror():
    """
    T2-A: SQSClient MUST raise ValueError when SQS_QUEUE_URL is missing.

    Ops Hardening v2: No hardcoded "localhost:4566/..." default.
    """
    # No SQS_QUEUE_URL
    env = {}

    with patch.dict("os.environ", env, clear=True):
        from dpp_api.queue.sqs_client import SQSClient

        with pytest.raises(ValueError, match="SQS_QUEUE_URL"):
            SQSClient()


def test_sqs_client_production_no_endpoint_no_test_creds():
    """
    T2-B: SQSClient in production (no SQS_ENDPOINT_URL) MUST NOT inject test credentials.

    Expected behavior:
    - boto3.client("sqs") called WITHOUT endpoint_url
    - boto3.client("sqs") called WITHOUT aws_access_key_id="test"
    """
    env = {
        "SQS_QUEUE_URL": "https://sqs.us-east-1.amazonaws.com/123456789/dpp-runs",
        # NO SQS_ENDPOINT_URL
    }

    with patch.dict("os.environ", env, clear=True):
        with patch("dpp_api.queue.sqs_client.boto3.client") as mock_boto3_client:
            mock_boto3_client.return_value = MagicMock()

            from dpp_api.queue.sqs_client import SQSClient

            client = SQSClient()

            # Verify boto3.client called
            assert mock_boto3_client.called
            call_kwargs = mock_boto3_client.call_args[1]

            # T2-B: NO endpoint_url in production
            assert "endpoint_url" not in call_kwargs or call_kwargs["endpoint_url"] is None
            # T2-B: NO test credentials
            assert call_kwargs.get("aws_access_key_id") != "test"


def test_sqs_client_localstack_with_test_creds():
    """
    T2-C: SQSClient with LocalStack endpoint MUST inject test credentials.

    When SQS_ENDPOINT_URL=http://localstack:4566 and NO AWS_ACCESS_KEY_ID:
    - boto3.client("sqs") called WITH endpoint_url
    - boto3.client("sqs") called WITH aws_access_key_id="test"
    """
    env = {
        "SQS_QUEUE_URL": "http://localstack:4566/000000000000/dpp-runs",
        "SQS_ENDPOINT_URL": "http://localstack:4566",
        # NO AWS_ACCESS_KEY_ID -> should trigger test creds injection
    }

    with patch.dict("os.environ", env, clear=True):
        with patch("dpp_api.queue.sqs_client.boto3.client") as mock_boto3_client:
            mock_boto3_client.return_value = MagicMock()

            from dpp_api.queue.sqs_client import SQSClient

            client = SQSClient()

            call_kwargs = mock_boto3_client.call_args[1]

            # T2-C: LocalStack endpoint_url present
            assert call_kwargs["endpoint_url"] == "http://localstack:4566"
            # T2-C: Test credentials injected
            assert call_kwargs["aws_access_key_id"] == "test"
            assert call_kwargs["aws_secret_access_key"] == "test"


def test_sqs_client_localstack_detection_all_markers():
    """
    T2-D: SQSClient MUST detect all 4 LocalStack markers.

    Markers: localhost, 127.0.0.1, localstack, host.docker.internal
    """
    test_cases = [
        ("http://localhost:4566", True),
        ("http://127.0.0.1:4566", True),
        ("http://localstack:4566", True),
        ("http://host.docker.internal:4566", True),
        ("https://sqs.us-east-1.amazonaws.com", False),
    ]

    for endpoint, expected_test_creds in test_cases:
        env = {
            "SQS_QUEUE_URL": "http://test/queue",
            "SQS_ENDPOINT_URL": endpoint,
            # NO AWS_ACCESS_KEY_ID
        }

        with patch.dict("os.environ", env, clear=True):
            with patch("dpp_api.queue.sqs_client.boto3.client") as mock_boto3_client:
                mock_boto3_client.return_value = MagicMock()

                from dpp_api.queue.sqs_client import SQSClient

                client = SQSClient()

                call_kwargs = mock_boto3_client.call_args[1]

                has_test_creds = call_kwargs.get("aws_access_key_id") == "test"

                assert has_test_creds == expected_test_creds, (
                    f"Endpoint {endpoint} -> expected_test_creds={expected_test_creds}, "
                    f"got has_test_creds={has_test_creds}"
                )


# ========================================================================
# T3: Supabase Production Guardrails (P0-1, P0-2, P0-3, P0-4)
# ========================================================================


class TestSupabaseProductionGuardrails:
    """Test Supabase production guardrails without actual DB connections."""

    def setup_method(self):
        """Clear all relevant env vars before each test."""
        env_vars = [
            "DP_ENV",
            "DPP_SUPABASE_ALLOW_NON_6543",
            "DPP_SUPABASE_ALLOW_DIRECT",
            "DPP_ALLOW_SUPABASE_API_KEYS",
            "DPP_ACK_BYPASS",
            "DPP_ACK_SUPABASE_NETWORK_RESTRICTIONS",
            "DPP_ACK_SUPABASE_BACKUP_POLICY",
            "SUPABASE_SERVICE_ROLE_KEY",
            "SUPABASE_ANON_KEY",
        ]
        for var in env_vars:
            os.environ.pop(var, None)

    def test_dev_env_skips_guardrails(self):
        """T3-A: DEV environment skips all guardrails."""
        os.environ["DP_ENV"] = "dev"
        url = "postgres://user:pass@db.pooler.supabase.com:5432/postgres"  # Bad config
        # Should not raise (DEV mode)
        _validate_supabase_production_config(url, "dev")

    def test_prod_non_supabase_skips_guardrails(self):
        """T3-B: PROD with non-Supabase host skips guardrails."""
        os.environ["DP_ENV"] = "prod"
        url = "postgres://user:pass@localhost:5432/dpp"
        # Should not raise (not Supabase)
        _validate_supabase_production_config(url, "prod")

    def test_prod_supabase_missing_sslmode_fails(self):
        """T3-C: PROD + Supabase without sslmode=require fails."""
        os.environ["DP_ENV"] = "prod"
        url = "postgres://user:pass@db.pooler.supabase.com:6543/postgres"
        with pytest.raises(RuntimeError, match="sslmode=require"):
            _validate_supabase_production_config(url, "prod")

    def test_prod_supabase_port_5432_fails(self):
        """T3-D: PROD + Supabase port 5432 (direct) fails without override."""
        os.environ["DP_ENV"] = "prod"
        url = "postgres://user:pass@db.supabase.co:5432/postgres?sslmode=require"
        with pytest.raises(RuntimeError, match="port must be 6543"):
            _validate_supabase_production_config(url, "prod")

    def test_prod_supabase_port_5432_with_override_passes(self):
        """T3-E: PROD + Supabase port 5432 with override passes."""
        os.environ["DP_ENV"] = "prod"
        os.environ["DPP_SUPABASE_ALLOW_NON_6543"] = "1"
        os.environ["DPP_ACK_SUPABASE_NETWORK_RESTRICTIONS"] = "1"
        os.environ["DPP_ACK_SUPABASE_BACKUP_POLICY"] = "1"
        url = "postgres://user:pass@db.pooler.supabase.com:5432/postgres?sslmode=require"
        # Should not raise (override enabled + ACKs set)
        _validate_supabase_production_config(url, "prod")

    def test_prod_supabase_non_pooler_host_fails(self):
        """T3-F: PROD + Supabase non-pooler host fails without override."""
        os.environ["DP_ENV"] = "prod"
        url = "postgres://user:pass@db.supabase.co:6543/postgres?sslmode=require"
        with pytest.raises(RuntimeError, match="must include 'pooler'"):
            _validate_supabase_production_config(url, "prod")

    def test_prod_supabase_non_pooler_with_override_passes(self):
        """T3-G: PROD + Supabase non-pooler with override passes."""
        os.environ["DP_ENV"] = "prod"
        os.environ["DPP_SUPABASE_ALLOW_DIRECT"] = "1"
        os.environ["DPP_ACK_SUPABASE_NETWORK_RESTRICTIONS"] = "1"
        os.environ["DPP_ACK_SUPABASE_BACKUP_POLICY"] = "1"
        url = "postgres://user:pass@db.supabase.co:6543/postgres?sslmode=require"
        # Should not raise (override enabled + ACKs set)
        _validate_supabase_production_config(url, "prod")

    def test_prod_supabase_api_key_present_fails(self):
        """T3-H: PROD + SUPABASE_SERVICE_ROLE_KEY present fails."""
        os.environ["DP_ENV"] = "prod"
        os.environ["SUPABASE_SERVICE_ROLE_KEY"] = "fake-key"
        url = "postgres://user:pass@db.pooler.supabase.com:6543/postgres?sslmode=require"
        with pytest.raises(RuntimeError, match="SUPABASE_SERVICE_ROLE_KEY"):
            _validate_supabase_production_config(url, "prod")

    def test_prod_supabase_api_key_with_override_passes(self):
        """T3-I: PROD + SUPABASE_SERVICE_ROLE_KEY with override passes."""
        os.environ["DP_ENV"] = "prod"
        os.environ["SUPABASE_SERVICE_ROLE_KEY"] = "fake-key"
        os.environ["DPP_ALLOW_SUPABASE_API_KEYS"] = "1"
        os.environ["DPP_ACK_SUPABASE_NETWORK_RESTRICTIONS"] = "1"
        os.environ["DPP_ACK_SUPABASE_BACKUP_POLICY"] = "1"
        url = "postgres://user:pass@db.pooler.supabase.com:6543/postgres?sslmode=require"
        # Should not raise (override enabled + ACKs set)
        _validate_supabase_production_config(url, "prod")

    def test_prod_supabase_missing_network_ack_fails(self):
        """T3-J: PROD + Supabase without Network ACK fails."""
        os.environ["DP_ENV"] = "prod"
        os.environ["DPP_ACK_SUPABASE_BACKUP_POLICY"] = "1"  # Only one ACK set
        url = "postgres://user:pass@db.pooler.supabase.com:6543/postgres?sslmode=require"
        with pytest.raises(RuntimeError, match="DPP_ACK_SUPABASE_NETWORK_RESTRICTIONS"):
            _validate_supabase_production_config(url, "prod")

    def test_prod_supabase_missing_backup_ack_fails(self):
        """T3-K: PROD + Supabase without Backup ACK fails."""
        os.environ["DP_ENV"] = "prod"
        os.environ["DPP_ACK_SUPABASE_NETWORK_RESTRICTIONS"] = "1"  # Only one ACK set
        url = "postgres://user:pass@db.pooler.supabase.com:6543/postgres?sslmode=require"
        with pytest.raises(RuntimeError, match="DPP_ACK_SUPABASE_BACKUP_POLICY"):
            _validate_supabase_production_config(url, "prod")

    def test_prod_supabase_ack_bypass_passes(self):
        """T3-L: PROD + Supabase with ACK bypass passes."""
        os.environ["DP_ENV"] = "prod"
        os.environ["DPP_ACK_BYPASS"] = "1"
        url = "postgres://user:pass@db.pooler.supabase.com:6543/postgres?sslmode=require"
        # Should not raise (ACK bypass enabled)
        _validate_supabase_production_config(url, "prod")

    def test_prod_supabase_full_valid_config_passes(self):
        """T3-M: PROD + Supabase with all requirements met passes."""
        os.environ["DP_ENV"] = "prod"
        os.environ["DPP_ACK_SUPABASE_NETWORK_RESTRICTIONS"] = "1"
        os.environ["DPP_ACK_SUPABASE_BACKUP_POLICY"] = "1"
        url = "postgres://user:pass@aws-0-us-east-1.pooler.supabase.com:6543/postgres?sslmode=require"
        # Should not raise (all requirements met)
        _validate_supabase_production_config(url, "prod")

    def test_prod_supabase_missing_port_fails(self):
        """T3-N: PROD + Supabase without explicit port fails."""
        os.environ["DP_ENV"] = "prod"
        url = "postgres://user:pass@db.pooler.supabase.com/postgres?sslmode=require"
        with pytest.raises(RuntimeError, match="must explicitly specify port"):
            _validate_supabase_production_config(url, "prod")
