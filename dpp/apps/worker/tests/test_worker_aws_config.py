"""
P0-A: Worker AWS client configuration tests.

Verify that worker does NOT inject test credentials in production,
and ONLY injects them for LocalStack environments.
"""

import os
from unittest.mock import MagicMock, patch

import pytest


def test_production_no_endpoint_no_test_creds():
    """
    P0-A Case A: Production-like environment.

    When NO SQS_ENDPOINT_URL/S3_ENDPOINT_URL are set:
    - boto3.client must be called WITHOUT endpoint_url
    - boto3.client must NOT have test credentials injected
    """
    env = {
        "SQS_QUEUE_URL": "https://sqs.us-east-1.amazonaws.com/123456789/dpp-runs",
        "S3_RESULT_BUCKET": "dpp-results-production",
        "DATABASE_URL": "postgresql://user:pass@db:5432/dpp",
        # NO SQS_ENDPOINT_URL, NO S3_ENDPOINT_URL
    }

    with patch.dict("os.environ", env, clear=True):
        with patch("dpp_worker.main.boto3.client") as mock_boto3_client:
            mock_boto3_client.return_value = MagicMock()

            # Import after patching env
            from dpp_worker.main import main

            # Mock other dependencies to avoid actual startup
            with patch("dpp_worker.main.create_engine"), \
                 patch("dpp_worker.main.RedisClient.get_client"), \
                 patch("dpp_worker.main.WorkerLoop"), \
                 patch("builtins.open", MagicMock()):

                try:
                    main()
                except (SystemExit, KeyboardInterrupt):
                    pass

            # Verify boto3.client calls
            assert mock_boto3_client.call_count >= 2  # SQS + S3

            # Check SQS call
            sqs_calls = [call for call in mock_boto3_client.call_args_list if call[0][0] == "sqs"]
            assert len(sqs_calls) == 1
            sqs_kwargs = sqs_calls[0][1]

            # P0-A: NO endpoint_url in production
            assert "endpoint_url" not in sqs_kwargs or sqs_kwargs["endpoint_url"] is None
            # P0-A: NO test credentials
            assert "aws_access_key_id" not in sqs_kwargs
            assert "aws_secret_access_key" not in sqs_kwargs

            # Check S3 call
            s3_calls = [call for call in mock_boto3_client.call_args_list if call[0][0] == "s3"]
            assert len(s3_calls) == 1
            s3_kwargs = s3_calls[0][1]

            # P0-A: NO endpoint_url in production
            assert "endpoint_url" not in s3_kwargs or s3_kwargs["endpoint_url"] is None
            # P0-A: NO test credentials
            assert "aws_access_key_id" not in s3_kwargs
            assert "aws_secret_access_key" not in s3_kwargs


def test_localstack_with_test_creds():
    """
    P0-A Case B: LocalStack environment.

    When SQS_ENDPOINT_URL=http://localhost:4566 and NO AWS_ACCESS_KEY_ID:
    - boto3.client must be called WITH endpoint_url
    - boto3.client must have test credentials injected
    """
    env = {
        "SQS_QUEUE_URL": "http://localhost:4566/000000000000/dpp-runs",
        "SQS_ENDPOINT_URL": "http://localhost:4566",
        "S3_ENDPOINT_URL": "http://localhost:4566",
        "S3_RESULT_BUCKET": "dpp-results",
        "DATABASE_URL": "postgresql://user:pass@localhost:5432/dpp",
        # NO AWS_ACCESS_KEY_ID -> should trigger test creds injection
    }

    with patch.dict("os.environ", env, clear=True):
        with patch("dpp_worker.main.boto3.client") as mock_boto3_client:
            mock_boto3_client.return_value = MagicMock()

            # Import after patching env
            from dpp_worker.main import main

            # Mock other dependencies
            with patch("dpp_worker.main.create_engine"), \
                 patch("dpp_worker.main.RedisClient.get_client"), \
                 patch("dpp_worker.main.WorkerLoop"), \
                 patch("builtins.open", MagicMock()):

                try:
                    main()
                except (SystemExit, KeyboardInterrupt):
                    pass

            # Check SQS call
            sqs_calls = [call for call in mock_boto3_client.call_args_list if call[0][0] == "sqs"]
            assert len(sqs_calls) == 1
            sqs_kwargs = sqs_calls[0][1]

            # P0-A: LocalStack endpoint_url present
            assert "endpoint_url" in sqs_kwargs
            assert sqs_kwargs["endpoint_url"] == "http://localhost:4566"
            # P0-A: Test credentials injected
            assert sqs_kwargs["aws_access_key_id"] == "test"
            assert sqs_kwargs["aws_secret_access_key"] == "test"

            # Check S3 call
            s3_calls = [call for call in mock_boto3_client.call_args_list if call[0][0] == "s3"]
            assert len(s3_calls) == 1
            s3_kwargs = s3_calls[0][1]

            # P0-A: LocalStack endpoint_url present
            assert "endpoint_url" in s3_kwargs
            assert s3_kwargs["endpoint_url"] == "http://localhost:4566"
            # P0-A: Test credentials injected
            assert s3_kwargs["aws_access_key_id"] == "test"
            assert s3_kwargs["aws_secret_access_key"] == "test"


def test_localstack_markers():
    """
    P0-A: Enhanced LocalStack detection.

    Verify that is_localstack() detects all local markers:
    - localhost
    - 127.0.0.1
    - localstack
    - host.docker.internal
    """
    env = {
        "SQS_QUEUE_URL": "http://test/queue",
        "S3_RESULT_BUCKET": "test-bucket",
        "DATABASE_URL": "postgresql://user:pass@db:5432/dpp",
    }

    test_cases = [
        ("http://localhost:4566", True),
        ("http://127.0.0.1:4566", True),
        ("http://localstack:4566", True),
        ("http://host.docker.internal:4566", True),
        ("https://sqs.us-east-1.amazonaws.com", False),
        ("https://s3.amazonaws.com", False),
    ]

    for endpoint, expected_localstack in test_cases:
        env_with_endpoint = {**env, "SQS_ENDPOINT_URL": endpoint}

        with patch.dict("os.environ", env_with_endpoint, clear=True):
            with patch("dpp_worker.main.boto3.client") as mock_boto3_client:
                mock_boto3_client.return_value = MagicMock()

                from dpp_worker.main import main

                with patch("dpp_worker.main.create_engine"), \
                     patch("dpp_worker.main.RedisClient.get_client"), \
                     patch("dpp_worker.main.WorkerLoop"), \
                     patch("builtins.open", MagicMock()):

                    try:
                        main()
                    except (SystemExit, KeyboardInterrupt):
                        pass

                # Check if test credentials were injected
                sqs_calls = [call for call in mock_boto3_client.call_args_list if call[0][0] == "sqs"]
                assert len(sqs_calls) == 1
                sqs_kwargs = sqs_calls[0][1]

                has_test_creds = "aws_access_key_id" in sqs_kwargs and sqs_kwargs["aws_access_key_id"] == "test"

                assert has_test_creds == expected_localstack, \
                    f"Endpoint {endpoint} -> expected_localstack={expected_localstack}, got has_test_creds={has_test_creds}"


def test_missing_sqs_queue_url_fails():
    """
    P0-A: Worker must fail-fast if SQS_QUEUE_URL is not set.
    """
    env = {
        "S3_RESULT_BUCKET": "test-bucket",
        "DATABASE_URL": "postgresql://user:pass@db:5432/dpp",
        # NO SQS_QUEUE_URL
    }

    with patch.dict("os.environ", env, clear=True):
        from dpp_worker.main import main

        with pytest.raises(ValueError, match="SQS_QUEUE_URL is required"):
            main()


def test_missing_s3_result_bucket_fails():
    """
    P0-B: Worker must fail-fast if S3_RESULT_BUCKET (or DPP_RESULTS_BUCKET) is not set.
    """
    env = {
        "SQS_QUEUE_URL": "http://localhost:4566/queue",
        "DATABASE_URL": "postgresql://user:pass@db:5432/dpp",
        # NO S3_RESULT_BUCKET or DPP_RESULTS_BUCKET
    }

    with patch.dict("os.environ", env, clear=True):
        from dpp_worker.main import main

        with pytest.raises(ValueError, match="S3_RESULT_BUCKET"):
            main()


def test_backward_compat_dpp_results_bucket():
    """
    P0-B: Worker must accept DPP_RESULTS_BUCKET for backward compatibility.
    """
    env = {
        "SQS_QUEUE_URL": "http://localhost:4566/queue",
        "SQS_ENDPOINT_URL": "http://localhost:4566",
        "DPP_RESULTS_BUCKET": "legacy-bucket-name",  # Legacy env var
        "DATABASE_URL": "postgresql://user:pass@db:5432/dpp",
    }

    with patch.dict("os.environ", env, clear=True):
        with patch("dpp_worker.main.boto3.client") as mock_boto3_client:
            mock_boto3_client.return_value = MagicMock()

            from dpp_worker.main import main

            with patch("dpp_worker.main.create_engine"), \
                 patch("dpp_worker.main.RedisClient.get_client"), \
                 patch("dpp_worker.main.WorkerLoop") as mock_worker_loop, \
                 patch("builtins.open", MagicMock()):

                try:
                    main()
                except (SystemExit, KeyboardInterrupt):
                    pass

                # Verify WorkerLoop was initialized with legacy bucket name
                assert mock_worker_loop.called
                init_kwargs = mock_worker_loop.call_args[1]
                assert init_kwargs["result_bucket"] == "legacy-bucket-name"
