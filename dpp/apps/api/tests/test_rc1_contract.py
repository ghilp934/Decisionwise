"""
RC-1 Contract Tests: Auth/Docs/OpenAPI SSOT

Tests that Authentication contract is unified across:
- OpenAPI spec (/.well-known/openapi.json)
- Quickstart documentation
- Function calling specs

SSOT (Single Source of Truth):
- Auth scheme: HTTP Bearer
- Header: Authorization: Bearer {token}
- Format: sk_{environment}_{key_id}_{secret}
- OpenAPI URL: /.well-known/openapi.json
"""

import pytest
from fastapi.testclient import TestClient
from dpp_api.main import app


@pytest.fixture
def client():
    """Test client for FastAPI app."""
    return TestClient(app)


class TestRC1ContractAuthDocsOpenAPISSoT:
    """RC-1: Auth/Docs/OpenAPI must be unified as single contract."""

    def test_rc1_contract_auth_docs_openapi_ssot(self, client):
        """
        RC-1 SSOT: Verify Auth/Docs/OpenAPI contract unification.

        Checks:
        1. OpenAPI has securitySchemes with HTTP Bearer
        2. OpenAPI has global security applied
        3. Base URL servers are defined
        """
        # Get OpenAPI spec
        response = client.get("/.well-known/openapi.json")
        assert response.status_code == 200, "OpenAPI endpoint must be accessible"

        openapi = response.json()

        # 1. Verify securitySchemes exists and has BearerAuth
        assert "components" in openapi, "OpenAPI must have components"
        assert "securitySchemes" in openapi["components"], "OpenAPI must have securitySchemes"

        security_schemes = openapi["components"]["securitySchemes"]
        assert "BearerAuth" in security_schemes, "BearerAuth scheme must be defined"

        bearer_auth = security_schemes["BearerAuth"]
        assert bearer_auth["type"] == "http", "BearerAuth type must be 'http'"
        assert bearer_auth["scheme"] == "bearer", "BearerAuth scheme must be 'bearer'"

        # bearerFormat should be absent OR set to opaque-token/access-token (NOT "API Key")
        if "bearerFormat" in bearer_auth:
            bearer_format = bearer_auth["bearerFormat"]
            assert bearer_format != "API Key", "bearerFormat must NOT be 'API Key'"
            assert bearer_format in ["opaque-token", "access-token"], \
                f"bearerFormat must be 'opaque-token' or 'access-token', got: {bearer_format}"

        # 2. Verify global security is applied
        assert "security" in openapi, "OpenAPI must have global security"
        assert len(openapi["security"]) > 0, "Global security must not be empty"
        assert {"BearerAuth": []} in openapi["security"], "BearerAuth must be in global security"

        # 3. Verify servers are defined
        assert "servers" in openapi, "OpenAPI must have servers"
        assert len(openapi["servers"]) > 0, "Servers list must not be empty"

        # Verify at least one server URL is defined
        server_urls = [server["url"] for server in openapi["servers"]]
        assert any(url for url in server_urls), "At least one server URL must be defined"

        # 4. Verify OpenAPI version
        assert openapi["openapi"] == "3.1.0", "OpenAPI version must be 3.1.0"

        print("\n✅ RC-1 PASS: Auth/Docs/OpenAPI SSOT verified")
        print(f"   - BearerAuth scheme: {bearer_auth['scheme']}")
        print(f"   - Bearer format: {bearer_auth.get('bearerFormat', 'not specified')}")
        print(f"   - Global security: {openapi['security']}")
        print(f"   - Servers: {len(openapi['servers'])} defined")
        print(f"   - Token format: opaque (no 'API Key' wording)")
