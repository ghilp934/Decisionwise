"""
T1: RateLimit middleware non-override regression test.

P0-4: Verify that handler-set RateLimit headers are not overridden by middleware.
"""

import pytest
from fastapi import APIRouter, Response
from fastapi.testclient import TestClient


def test_ratelimit_middleware_respects_handler_headers(monkeypatch):
    """
    T1: RateLimit middleware MUST NOT override headers set by handlers.

    P0-4 Contract:
    - If handler sets RateLimit-Policy/RateLimit, middleware preserves them
    - If handler does NOT set them, middleware adds default headers
    """
    from fastapi import FastAPI
    from dpp_api.rate_limiter import NoOpRateLimiter

    # Create a standalone test app with rate limit middleware
    test_app = FastAPI()

    # Add NoOpRateLimiter for predictable behavior
    test_app.state.rate_limiter = NoOpRateLimiter(quota=60, window=60)

    # Create test router with custom RateLimit headers
    test_router = APIRouter()

    @test_router.get("/v1/test-custom-ratelimit")
    def custom_ratelimit_handler(response: Response):
        """Handler that sets custom RateLimit headers."""
        response.headers["RateLimit-Policy"] = '"custom"; q=100; w=3600'
        response.headers["RateLimit"] = '"custom"; r=99; t=3500'
        return {"message": "custom headers set"}

    @test_router.get("/v1/test-no-ratelimit")
    def no_ratelimit_handler():
        """Handler that does NOT set RateLimit headers."""
        return {"message": "no custom headers"}

    @test_router.get("/v1/test-policy-only")
    def policy_only_handler(response: Response):
        """Handler that sets ONLY RateLimit-Policy."""
        response.headers["RateLimit-Policy"] = '"custom-policy"; q=200; w=7200'
        return {"message": "policy only"}

    @test_router.get("/v1/test-limit-only")
    def limit_only_handler(response: Response):
        """Handler that sets ONLY RateLimit."""
        response.headers["RateLimit"] = '"custom-limit"; r=150; t=5000'
        return {"message": "limit only"}

    # Include router before adding middleware
    test_app.include_router(test_router)

    # Add rate limit middleware (simplified version of main.py logic)
    @test_app.middleware("http")
    async def rate_limit_middleware(request, call_next):
        response = await call_next(request)

        # P1-C: Add headers for successful responses (fill missing only)
        if 200 <= response.status_code < 300:
            # Check if handler already set RateLimit headers
            handler_set_policy = "RateLimit-Policy" in response.headers
            handler_set_limit = "RateLimit" in response.headers

            # Fill missing headers (preserve handler-set values)
            if not handler_set_policy or not handler_set_limit:
                rate_limiter = test_app.state.rate_limiter
                result = rate_limiter.check_rate_limit(key="test", path=str(request.url.path))

                if not handler_set_policy:
                    rate_limit_policy = f'"{result.policy_id}"; q={result.quota}; w={result.window}'
                    response.headers["RateLimit-Policy"] = rate_limit_policy

                if not handler_set_limit:
                    rate_limit = f'"{result.policy_id}"; r={result.remaining}; t={result.reset}'
                    response.headers["RateLimit"] = rate_limit

        return response

    client = TestClient(test_app)

    # Test 1: Handler sets custom headers -> middleware preserves them
    resp1 = client.get("/v1/test-custom-ratelimit")
    assert resp1.status_code == 200
    assert resp1.headers["RateLimit-Policy"] == '"custom"; q=100; w=3600'
    assert resp1.headers["RateLimit"] == '"custom"; r=99; t=3500'

    # Test 2: Handler does NOT set headers -> middleware adds defaults
    resp2 = client.get("/v1/test-no-ratelimit")
    assert resp2.status_code == 200
    assert "RateLimit-Policy" in resp2.headers
    assert "RateLimit" in resp2.headers
    # Defaults from NoOpRateLimiter (quota=60, window=60)
    assert 'q=60' in resp2.headers["RateLimit-Policy"]
    assert 'w=60' in resp2.headers["RateLimit-Policy"]

    # Test 3: Handler sets ONLY Policy -> middleware adds default Limit
    resp3 = client.get("/v1/test-policy-only")
    assert resp3.status_code == 200
    # Handler-set Policy preserved
    assert resp3.headers["RateLimit-Policy"] == '"custom-policy"; q=200; w=7200'
    # Middleware-added default Limit
    assert "RateLimit" in resp3.headers
    assert 'default' in resp3.headers["RateLimit"]
    assert 'r=' in resp3.headers["RateLimit"]

    # Test 4: Handler sets ONLY Limit -> middleware adds default Policy
    resp4 = client.get("/v1/test-limit-only")
    assert resp4.status_code == 200
    # Handler-set Limit preserved
    assert resp4.headers["RateLimit"] == '"custom-limit"; r=150; t=5000'
    # Middleware-added default Policy
    assert "RateLimit-Policy" in resp4.headers
    assert 'default' in resp4.headers["RateLimit-Policy"]
    assert 'q=60' in resp4.headers["RateLimit-Policy"]
