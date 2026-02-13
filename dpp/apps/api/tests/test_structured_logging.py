"""Tests for Structured Logging with Context (MS-6).

Validates that all logs include run_id and tenant_id for 1-minute root cause analysis.
"""

import json
import logging
from io import StringIO

import pytest

from dpp_api.context import request_id_var, run_id_var, tenant_id_var
from dpp_api.utils.logging import JSONFormatter, configure_json_logging


def test_json_formatter_includes_context_vars() -> None:
    """Test that JSONFormatter automatically includes run_id and tenant_id from context."""
    # Setup logger with JSON formatter
    logger = logging.getLogger("test_context_logger")
    logger.setLevel(logging.INFO)
    logger.handlers.clear()

    stream = StringIO()
    handler = logging.StreamHandler(stream)
    handler.setFormatter(JSONFormatter())
    logger.addHandler(handler)

    # Set context variables (MS-6)
    request_id_var.set("req_123")
    run_id_var.set("run_abc")
    tenant_id_var.set("tenant_xyz")

    # Log a message
    logger.info("Test message")

    # Parse JSON output
    output = stream.getvalue()
    log_data = json.loads(output)

    # MS-6: CRITICAL - All logs must include run_id and tenant_id
    assert log_data["message"] == "Test message"
    assert log_data["request_id"] == "req_123"
    assert log_data["run_id"] == "run_abc", "MS-6: run_id MUST be in all logs"
    assert log_data["tenant_id"] == "tenant_xyz", "MS-6: tenant_id MUST be in all logs"


def test_json_formatter_handles_missing_context() -> None:
    """Test that JSONFormatter handles missing context variables gracefully."""
    # Clear context variables from previous tests (MS-6: isolation)
    request_id_var.set("")
    run_id_var.set("")
    tenant_id_var.set("")

    logger = logging.getLogger("test_no_context_logger")
    logger.setLevel(logging.INFO)
    logger.handlers.clear()

    stream = StringIO()
    handler = logging.StreamHandler(stream)
    handler.setFormatter(JSONFormatter())
    logger.addHandler(handler)

    # Don't set any context variables
    # (This happens in non-request contexts like background tasks)

    # Log a message
    logger.info("Background task message")

    # Parse JSON output
    output = stream.getvalue()
    log_data = json.loads(output)

    # Should work without context
    assert log_data["message"] == "Background task message"
    # Context fields should be absent (not empty strings)
    assert "run_id" not in log_data
    assert "tenant_id" not in log_data


def test_json_formatter_includes_extra_fields() -> None:
    """Test that extra fields from logger.info(..., extra={...}) are included."""
    logger = logging.getLogger("test_extra_logger")
    logger.setLevel(logging.INFO)
    logger.handlers.clear()

    stream = StringIO()
    handler = logging.StreamHandler(stream)
    handler.setFormatter(JSONFormatter())
    logger.addHandler(handler)

    # Set context
    run_id_var.set("run_extra_123")
    tenant_id_var.set("tenant_extra_456")

    # Log with extra fields (MS-6: for detailed debugging)
    logger.info(
        "Budget reserve failed",
        extra={
            "error_code": "INSUFFICIENT_BUDGET",
            "requested_micros": 500000,
            "available_micros": 100000,
        }
    )

    # Parse JSON output
    output = stream.getvalue()
    log_data = json.loads(output)

    # Context automatically included (MS-6)
    assert log_data["run_id"] == "run_extra_123"
    assert log_data["tenant_id"] == "tenant_extra_456"

    # Extra fields also included
    assert log_data["error_code"] == "INSUFFICIENT_BUDGET"
    assert log_data["requested_micros"] == 500000
    assert log_data["available_micros"] == 100000


def test_json_formatter_includes_exception_info() -> None:
    """Test that exception info is properly formatted in JSON."""
    logger = logging.getLogger("test_exception_logger")
    logger.setLevel(logging.ERROR)
    logger.handlers.clear()

    stream = StringIO()
    handler = logging.StreamHandler(stream)
    handler.setFormatter(JSONFormatter())
    logger.addHandler(handler)

    # Set context
    run_id_var.set("run_exc_789")
    tenant_id_var.set("tenant_exc_012")

    # Log an exception
    try:
        raise ValueError("Test exception for logging")
    except ValueError:
        logger.error("Exception occurred", exc_info=True)

    # Parse JSON output
    output = stream.getvalue()
    log_data = json.loads(output)

    # Context included even in error logs
    assert log_data["run_id"] == "run_exc_789"
    assert log_data["tenant_id"] == "tenant_exc_012"

    # Exception info included
    assert "exc_info" in log_data
    assert "ValueError: Test exception for logging" in log_data["exc_info"]
    assert "Traceback" in log_data["exc_info"]


def test_configure_json_logging_sets_json_formatter() -> None:
    """Test that configure_json_logging sets up JSON formatter correctly."""
    # Configure JSON logging
    configure_json_logging(log_level="INFO")

    # Get root logger
    root_logger = logging.getLogger()

    # Should have at least one handler
    assert len(root_logger.handlers) > 0

    # Handler should use JSONFormatter
    handler = root_logger.handlers[0]
    assert isinstance(handler.formatter, JSONFormatter)


def test_log_fields_structure() -> None:
    """Test that log output has all required fields for observability.

    MS-6: Logs must be parseable by log aggregation tools (Elasticsearch, CloudWatch).
    """
    logger = logging.getLogger("test_structure_logger")
    logger.setLevel(logging.INFO)
    logger.handlers.clear()

    stream = StringIO()
    handler = logging.StreamHandler(stream)
    handler.setFormatter(JSONFormatter())
    logger.addHandler(handler)

    # Set full context
    request_id_var.set("req_full_999")
    run_id_var.set("run_full_888")
    tenant_id_var.set("tenant_full_777")

    # Log with trace_id (from extra)
    logger.info(
        "Complete log entry",
        extra={"trace_id": "trace_666"}
    )

    # Parse JSON output
    output = stream.getvalue()
    log_data = json.loads(output)

    # MS-6: Required fields for 1-minute root cause analysis
    required_fields = [
        "timestamp",      # When did it happen?
        "level",          # How severe?
        "message",        # What happened?
        "module",         # Where in code?
        "func",           # Which function?
        "line",           # Which line?
        "request_id",     # Which HTTP request?
        "run_id",         # Which run? (MS-6 CRITICAL)
        "tenant_id",      # Which tenant? (MS-6 CRITICAL)
        "trace_id",       # Distributed tracing
    ]

    for field in required_fields:
        assert field in log_data, f"MS-6: Required field '{field}' missing from log"

    # Timestamp should be ISO 8601 format
    assert "T" in log_data["timestamp"]
    assert log_data["timestamp"].endswith("+00:00") or log_data["timestamp"].endswith("Z")


def test_context_isolation_between_requests() -> None:
    """Test that context variables don't leak between requests.

    This is CRITICAL for multi-tenant systems.
    """
    logger = logging.getLogger("test_isolation_logger")
    logger.setLevel(logging.INFO)
    logger.handlers.clear()

    stream = StringIO()
    handler = logging.StreamHandler(stream)
    handler.setFormatter(JSONFormatter())
    logger.addHandler(handler)

    # Request 1
    run_id_var.set("run_request1")
    tenant_id_var.set("tenant_request1")
    logger.info("Request 1")

    output1 = stream.getvalue()
    log1 = json.loads(output1.strip().split("\n")[0])
    assert log1["run_id"] == "run_request1"
    assert log1["tenant_id"] == "tenant_request1"

    # Clear stream
    stream.truncate(0)
    stream.seek(0)

    # Request 2 (different context)
    run_id_var.set("run_request2")
    tenant_id_var.set("tenant_request2")
    logger.info("Request 2")

    output2 = stream.getvalue()
    log2 = json.loads(output2.strip())
    assert log2["run_id"] == "run_request2"
    assert log2["tenant_id"] == "tenant_request2"

    # Ensure no cross-contamination
    assert log2["run_id"] != log1["run_id"]
    assert log2["tenant_id"] != log1["tenant_id"]
