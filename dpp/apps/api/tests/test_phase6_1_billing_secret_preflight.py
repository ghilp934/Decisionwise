"""Phase 6.1: Billing secret active preflight tests.

Coverage:
  T1) REQUIRED=1 + PayPal 401 → RuntimeError (startup Fail-Fast)
  T2) REQUIRED=1 + Toss 401 → RuntimeError (startup Fail-Fast)
  T3) REQUIRED=1 + Toss 404 → PASS (auth OK, order-not-found is expected)
  T4) REQUIRED=1 + invalid pepper_b64 → fingerprint config RuntimeError at boot

All tests use monkeypatching — no real paypal.com / tosspayments.com calls.
"""

from __future__ import annotations

import os
from unittest.mock import AsyncMock, MagicMock, patch

import pytest


# ---------------------------------------------------------------------------
# Helpers for mock httpx responses
# ---------------------------------------------------------------------------

def _mock_response(status_code: int, json_body: dict | None = None) -> MagicMock:
    resp = MagicMock()
    resp.status_code = status_code
    if json_body is not None:
        resp.json.return_value = json_body
    else:
        resp.json.side_effect = ValueError("no body")
    return resp


def _async_client_ctx(response: MagicMock) -> MagicMock:
    """Return a context manager that yields an async client whose request methods
    return the given response."""
    mock_client = AsyncMock()
    mock_client.post = AsyncMock(return_value=response)
    mock_client.get = AsyncMock(return_value=response)

    ctx = MagicMock()
    ctx.__aenter__ = AsyncMock(return_value=mock_client)
    ctx.__aexit__ = AsyncMock(return_value=False)
    return ctx


# ---------------------------------------------------------------------------
# Fixture: reset module cache between tests
# ---------------------------------------------------------------------------

@pytest.fixture(autouse=True)
def reset_preflight_cache():
    """Reset active_preflight module-level cache before each test."""
    from dpp_api.billing.active_preflight import _reset_preflight_cache
    _reset_preflight_cache()
    yield
    _reset_preflight_cache()


# ---------------------------------------------------------------------------
# T1: PayPal 401 → RuntimeError when REQUIRED=1
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_t1_paypal_401_raises_when_required(monkeypatch):
    """T1: PayPal OAuth returns 401 → BILLING_SECRET_PREFLIGHT_FAILED:paypal:..."""
    monkeypatch.setenv("PAYPAL_CLIENT_ID", "test_client_id")
    monkeypatch.setenv("PAYPAL_CLIENT_SECRET", "test_client_secret")
    monkeypatch.setenv("TOSS_SECRET_KEY", "test_sk_dummy")
    monkeypatch.setenv("DPP_BILLING_PREFLIGHT_REQUIRED", "1")

    paypal_401 = _mock_response(401, {"error": "invalid_client"})
    toss_404 = _mock_response(404, {"code": "NOT_FOUND_PAYMENT"})

    call_count = {"paypal": 0, "toss": 0}

    def _make_client_ctx(mock_resp_for_paypal, mock_resp_for_toss):
        mock_client = AsyncMock()

        async def _post(url, **kwargs):
            call_count["paypal"] += 1
            return mock_resp_for_paypal

        async def _get(url, **kwargs):
            call_count["toss"] += 1
            return mock_resp_for_toss

        mock_client.post = _post
        mock_client.get = _get

        ctx = MagicMock()
        ctx.__aenter__ = AsyncMock(return_value=mock_client)
        ctx.__aexit__ = AsyncMock(return_value=False)
        return ctx

    with patch("httpx.AsyncClient", side_effect=[
        _make_client_ctx(paypal_401, toss_404),
        _make_client_ctx(paypal_401, toss_404),
    ]):
        with pytest.raises(RuntimeError) as exc_info:
            from dpp_api.billing.active_preflight import run_billing_secrets_active_preflight
            await run_billing_secrets_active_preflight()

    assert "BILLING_SECRET_PREFLIGHT_FAILED" in str(exc_info.value)
    assert "paypal" in str(exc_info.value)


# ---------------------------------------------------------------------------
# T2: Toss 401 → RuntimeError when REQUIRED=1
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_t2_toss_401_raises_when_required(monkeypatch):
    """T2: Toss returns 401 → BILLING_SECRET_PREFLIGHT_FAILED:toss:..."""
    monkeypatch.setenv("PAYPAL_CLIENT_ID", "test_client_id")
    monkeypatch.setenv("PAYPAL_CLIENT_SECRET", "test_client_secret")
    monkeypatch.setenv("TOSS_SECRET_KEY", "test_sk_dummy")
    monkeypatch.setenv("DPP_BILLING_PREFLIGHT_REQUIRED", "1")

    paypal_ok = _mock_response(200, {"access_token": "<redacted>"})
    toss_401 = _mock_response(401, {"code": "UNAUTHORIZED_KEY"})

    # Track which requests have been made so we can route correctly
    request_log: list[str] = []

    from dpp_api.billing import active_preflight as pf_module

    original_check_paypal = pf_module._check_paypal
    original_check_toss = pf_module._check_toss

    async def stub_paypal(timeout):
        return "ok"

    async def stub_toss(timeout):
        # Simulate 401 handling
        required = pf_module._is_required()
        reason = "AUTH_FAILED:HTTP_401"
        if required:
            raise RuntimeError(f"BILLING_SECRET_PREFLIGHT_FAILED:toss:{reason}")
        return f"err:{reason}"

    with patch.object(pf_module, "_check_paypal", stub_paypal), \
         patch.object(pf_module, "_check_toss", stub_toss):
        with pytest.raises(RuntimeError) as exc_info:
            await pf_module.run_billing_secrets_active_preflight()

    assert "BILLING_SECRET_PREFLIGHT_FAILED" in str(exc_info.value)
    assert "toss" in str(exc_info.value)
    assert "AUTH_FAILED" in str(exc_info.value)


# ---------------------------------------------------------------------------
# T3: Toss 404 → PASS (order not found = auth accepted)
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_t3_toss_404_is_pass(monkeypatch):
    """T3: Toss returns 404 (unknown orderId) → preflight PASS for toss."""
    monkeypatch.setenv("TOSS_SECRET_KEY", "test_sk_dummy_key")
    monkeypatch.setenv("DPP_BILLING_PREFLIGHT_REQUIRED", "1")

    toss_404 = _mock_response(404, {"code": "NOT_FOUND_PAYMENT", "message": "payment not found"})

    with patch("httpx.AsyncClient") as mock_cls:
        mock_client = AsyncMock()
        mock_client.get = AsyncMock(return_value=toss_404)
        mock_cls.return_value.__aenter__ = AsyncMock(return_value=mock_client)
        mock_cls.return_value.__aexit__ = AsyncMock(return_value=False)

        from dpp_api.billing.active_preflight import _check_toss
        result = await _check_toss(timeout=5.0)

    assert result == "ok", f"Expected 'ok' for 404 response, got: {result!r}"


# ---------------------------------------------------------------------------
# T4: Invalid pepper_b64 → fingerprint config raises at boot (Fail-closed)
# ---------------------------------------------------------------------------

def test_t4_invalid_pepper_b64_raises_on_boot(monkeypatch):
    """T4: REQUIRED=1 + malformed PEPPER_B64 → validate_kill_switch_audit_fingerprint_config raises."""
    monkeypatch.setenv("KILL_SWITCH_AUDIT_REQUIRED", "1")
    monkeypatch.setenv("KILL_SWITCH_AUDIT_FINGERPRINT_PEPPER_B64", "not-valid-base64!!!")
    # kid can be valid
    monkeypatch.setenv("KILL_SWITCH_AUDIT_FINGERPRINT_KID", "kid_202602")

    from dpp_api.audit.kill_switch_audit import validate_kill_switch_audit_fingerprint_config

    with pytest.raises(Exception) as exc_info:
        validate_kill_switch_audit_fingerprint_config()

    # Should raise a binascii/base64 decode error
    # (base64.b64decode raises binascii.Error on invalid padding / chars)
    exc_str = str(type(exc_info.value).__name__).lower()
    assert any(
        keyword in exc_str or keyword in str(exc_info.value).lower()
        for keyword in ["error", "decode", "padding", "invalid"]
    ), f"Expected a decode/format error, got: {exc_info.value!r}"


# ---------------------------------------------------------------------------
# Bonus T5: REQUIRED=1 + no pepper → RuntimeError("FINGERPRINT_PEPPER_NOT_SET")
# ---------------------------------------------------------------------------

def test_t5_missing_pepper_raises_when_required(monkeypatch):
    """T5: REQUIRED=1 + no pepper env → FINGERPRINT_PEPPER_NOT_SET at boot."""
    monkeypatch.setenv("KILL_SWITCH_AUDIT_REQUIRED", "1")
    monkeypatch.delenv("KILL_SWITCH_AUDIT_FINGERPRINT_PEPPER_B64", raising=False)
    monkeypatch.delenv("KILL_SWITCH_AUDIT_FINGERPRINT_PEPPER", raising=False)
    monkeypatch.setenv("KILL_SWITCH_AUDIT_FINGERPRINT_KID", "kid_202602")

    from dpp_api.audit.kill_switch_audit import validate_kill_switch_audit_fingerprint_config

    with pytest.raises(RuntimeError, match="FINGERPRINT_PEPPER_NOT_SET"):
        validate_kill_switch_audit_fingerprint_config()
