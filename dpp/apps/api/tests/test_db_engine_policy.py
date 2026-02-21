"""Test DB engine policy (Spec Lock: NullPool default + verify-full enforcement).

Ensures:
1. Default pool mode is NullPool (when DPP_DB_POOL not set)
2. QueuePool is used when DPP_DB_POOL=queuepool
3. Supabase PROD hosts require sslmode=verify-full
4. Production guardrail rejects unsafe modes (disable / allow / prefer)
5. Production guardrail rejects weaker modes (require) — updated from P0-SSL Phase 2
6. DPP_DB_SSLMODE env var is respected as SSOT (overrides URL sslmode)
7. verify-full without sslrootcert → RuntimeError (fail-fast)
"""

import os
import tempfile
from unittest.mock import patch

import pytest
from sqlalchemy import NullPool, QueuePool

from dpp_api.db.engine import build_engine


class TestDBEnginePolicy:
    """Test database engine builder policy (Spec Lock)."""

    def test_default_pool_is_nullpool(self):
        """Test A: Default pool policy is NullPool (no env override)."""
        # Arrange: Mock environment with Supabase pooler URL
        supabase_url = "postgresql://postgres.xyz:[PASSWORD]@aws-0-us-west-1.pooler.supabase.com:6543/postgres"

        with patch.dict(os.environ, {"DPP_DB_POOL": ""}, clear=False):
            # Act
            engine = build_engine(supabase_url)

            # Assert
            assert isinstance(
                engine.pool, NullPool
            ), f"Expected NullPool, got {engine.pool.__class__.__name__}"

    def test_queuepool_when_explicit(self):
        """Test B: QueuePool is used when DPP_DB_POOL=queuepool."""
        # Arrange
        test_url = "postgresql://user:pass@localhost:5432/testdb"

        with patch.dict(
            os.environ,
            {"DPP_DB_POOL": "queuepool", "DPP_DB_POOL_SIZE": "3", "DPP_DB_MAX_OVERFLOW": "5"},
            clear=False,
        ):
            # Act
            engine = build_engine(test_url)

            # Assert
            assert isinstance(
                engine.pool, QueuePool
            ), f"Expected QueuePool, got {engine.pool.__class__.__name__}"
            assert engine.pool.size() == 3, f"Expected pool_size=3, got {engine.pool.size()}"

    def test_supabase_host_enforces_ssl(self):
        """Test C: Supabase hosts enforce SSL — smoke test (actual SSL at connection time)."""
        # Arrange: Supabase pooler URL without sslmode
        supabase_url = "postgresql://postgres.xyz:[PASSWORD]@aws-0-us-west-1.pooler.supabase.com:6543/postgres"

        with patch.dict(os.environ, {"DPP_DB_POOL": "nullpool"}, clear=False):
            # Act
            engine = build_engine(supabase_url)

            # Assert: URL should be a Supabase host
            assert ".supabase.com" in supabase_url, "Test setup error: expected Supabase URL"
            assert engine is not None

    def test_invalid_pool_mode_raises(self):
        """Test D: Invalid DPP_DB_POOL value raises ValueError."""
        # Arrange
        test_url = "postgresql://user:pass@localhost:5432/testdb"

        with patch.dict(os.environ, {"DPP_DB_POOL": "invalidpool"}, clear=False):
            # Act & Assert
            with pytest.raises(ValueError, match="Invalid DPP_DB_POOL"):
                build_engine(test_url)

    def test_missing_database_url_raises(self):
        """Test E: Missing DATABASE_URL raises ValueError."""
        # Arrange: Clear DATABASE_URL
        with patch.dict(os.environ, {}, clear=True):
            # Remove DATABASE_URL if it exists
            os.environ.pop("DATABASE_URL", None)

            # Act & Assert
            with pytest.raises(ValueError, match="DATABASE_URL is required"):
                build_engine(None)


class TestProductionSSLGuardrail:
    """Test production SSL guardrail — verify-full required for PROD+Supabase.

    P0-SSL Phase 2 update:
      - PROD+Supabase MUST use sslmode=verify-full (require is no longer sufficient).
      - sslrootcert (CA bundle) MUST be present and readable for verify-full.
    """

    _PROD_ENV = {
        "DP_ENV": "production",
        "DPP_ACK_SUPABASE_NETWORK_RESTRICTIONS": "1",
        "DPP_ACK_SUPABASE_BACKUP_POLICY": "1",
    }

    # Class-level temp cert file.
    _ssl_cert_path: str = ""

    @classmethod
    def setup_class(cls):
        """Create a temporary CA cert file for tests that need verify-full."""
        with tempfile.NamedTemporaryFile(
            suffix=".crt", delete=False, mode="wb"
        ) as f:
            f.write(
                b"-----BEGIN CERTIFICATE-----\n"
                b"FAKE CERT FOR UNIT TESTING — NOT A REAL CA\n"
                b"-----END CERTIFICATE-----\n"
            )
            cls._ssl_cert_path = f.name

    @classmethod
    def teardown_class(cls):
        """Remove the temporary CA cert file."""
        try:
            os.unlink(cls._ssl_cert_path)
        except FileNotFoundError:
            pass

    def _pooler_url(self, sslmode: str | None = None) -> str:
        base = "postgresql://postgres.xyz:pw@aws-0-ap-northeast-2.pooler.supabase.com:6543/postgres"
        if sslmode:
            return f"{base}?sslmode={sslmode}"
        return base

    def _verify_full_env(self, extra: dict | None = None) -> dict:
        """Return env dict with verify-full + valid cert (+ optional extras)."""
        env = {
            **self._PROD_ENV,
            "DPP_DB_SSLMODE": "verify-full",
            "DPP_DB_SSLROOTCERT": self.__class__._ssl_cert_path,
        }
        if extra:
            env.update(extra)
        return env

    # -----------------------------------------------------------------------
    # Tests that SHOULD PASS (valid PROD config)
    # -----------------------------------------------------------------------

    def test_guardrail_accepts_verify_full_with_cert(self):
        """Production guardrail: DPP_DB_SSLMODE=verify-full + cert → OK."""
        with patch.dict(os.environ, self._verify_full_env(), clear=False):
            engine = build_engine(self._pooler_url())
            assert engine is not None

    def test_guardrail_accepts_verify_full_in_url_with_env_ssot(self):
        """Production guardrail: URL has verify-full, ENV also verify-full → OK (no conflict)."""
        with patch.dict(os.environ, self._verify_full_env(), clear=False):
            engine = build_engine(self._pooler_url("verify-full"))
            assert engine is not None

    def test_guardrail_rejects_verify_ca_in_prod(self):
        """Production guardrail: DPP_DB_SSLMODE=verify-ca → RuntimeError.

        PROD+Supabase requires exactly 'verify-full'. verify-ca is insufficient.
        """
        env = self._verify_full_env({"DPP_DB_SSLMODE": "verify-ca"})
        with patch.dict(os.environ, env, clear=False):
            with pytest.raises(RuntimeError, match="verify-full"):
                build_engine(self._pooler_url())

    # -----------------------------------------------------------------------
    # Tests that SHOULD FAIL (invalid PROD config)
    # -----------------------------------------------------------------------

    def test_guardrail_rejects_require_in_prod(self):
        """Production guardrail: DPP_DB_SSLMODE=require → RuntimeError.

        P0-SSL Phase 2: 'require' is no longer sufficient in PROD+Supabase.
        """
        env = {**self._PROD_ENV, "DPP_DB_SSLMODE": "require"}
        with patch.dict(os.environ, env, clear=False):
            with pytest.raises(RuntimeError, match="verify-full"):
                build_engine(self._pooler_url())

    def test_guardrail_rejects_require_in_url_no_env(self):
        """Production guardrail: URL sslmode=require, no DPP_DB_SSLMODE → RuntimeError."""
        with patch.dict(os.environ, self._PROD_ENV, clear=False):
            # No DPP_DB_SSLMODE → URL value used → "require" → fails
            with pytest.raises(RuntimeError, match="verify-full"):
                build_engine(self._pooler_url("require"))

    def test_guardrail_rejects_disable_in_url(self):
        """Production guardrail: sslmode=disable → RuntimeError."""
        with patch.dict(os.environ, self._PROD_ENV, clear=False):
            with pytest.raises(RuntimeError, match="verify-full"):
                build_engine(self._pooler_url("disable"))

    def test_guardrail_rejects_allow_in_url(self):
        """Production guardrail: sslmode=allow → RuntimeError."""
        with patch.dict(os.environ, self._PROD_ENV, clear=False):
            with pytest.raises(RuntimeError, match="verify-full"):
                build_engine(self._pooler_url("allow"))

    def test_guardrail_rejects_prefer_in_url(self):
        """Production guardrail: sslmode=prefer → RuntimeError."""
        with patch.dict(os.environ, self._PROD_ENV, clear=False):
            with pytest.raises(RuntimeError, match="verify-full"):
                build_engine(self._pooler_url("prefer"))

    def test_guardrail_rejects_verify_full_without_cert(self):
        """Production guardrail: DPP_DB_SSLMODE=verify-full but no sslrootcert → RuntimeError."""
        env = {
            **self._PROD_ENV,
            "DPP_DB_SSLMODE": "verify-full",
            # DPP_DB_SSLROOTCERT intentionally absent
        }
        with patch.dict(os.environ, env, clear=False):
            with pytest.raises(RuntimeError, match="sslrootcert"):
                build_engine(self._pooler_url())

    def test_guardrail_rejects_verify_full_with_missing_cert_file(self):
        """Production guardrail: DPP_DB_SSLMODE=verify-full + non-existent cert → RuntimeError."""
        env = {
            **self._PROD_ENV,
            "DPP_DB_SSLMODE": "verify-full",
            "DPP_DB_SSLROOTCERT": "/nonexistent/path/supabase-ca.crt",
        }
        with patch.dict(os.environ, env, clear=False):
            with pytest.raises(RuntimeError, match="sslrootcert"):
                build_engine(self._pooler_url())

    def test_dpp_db_sslmode_env_is_ssot_when_set(self):
        """DPP_DB_SSLMODE env var overrides URL sslmode when both are set (ENV is SSOT)."""
        env = self._verify_full_env()  # DPP_DB_SSLMODE=verify-full, cert present
        with patch.dict(os.environ, env, clear=False):
            # URL has no sslmode; ENV provides verify-full.
            engine = build_engine(self._pooler_url())
            assert engine is not None

    def test_dpp_db_sslmode_disable_rejected_in_prod(self):
        """DPP_DB_SSLMODE=disable in production → RuntimeError (even without URL sslmode)."""
        env = {**self._PROD_ENV, "DPP_DB_SSLMODE": "disable"}
        with patch.dict(os.environ, env, clear=False):
            with pytest.raises(RuntimeError, match="verify-full"):
                build_engine(self._pooler_url())  # URL has no sslmode; env says "disable"
