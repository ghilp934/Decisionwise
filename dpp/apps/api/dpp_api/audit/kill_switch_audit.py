"""P5.3/P5.9: Kill-switch audit record builder.

Records are written to the WORM sink BEFORE state is mutated.
Fail-closed semantics are enforced in the caller (admin router).

P5.9 additions:
  fingerprint_token() — HMAC-SHA256(pepper, token) with Key-ID prefix for rotation-ready
                        actor token fingerprinting. Format: "<kid>:<TRUNC_HEX>".
  Env vars:
    KILL_SWITCH_AUDIT_FINGERPRINT_KID         — Key-ID prefix (default: "kid_dev")
    KILL_SWITCH_AUDIT_FINGERPRINT_PEPPER_B64  — base64-encoded pepper (preferred production)
    KILL_SWITCH_AUDIT_FINGERPRINT_PEPPER      — utf-8 pepper (fallback / dev)

  IP addresses continue to use sha256 (_fingerprint); they are less sensitive than
  admin tokens and are not subject to the same rotation requirements.
"""

import base64
import hashlib
import hmac
import os
import re
from datetime import datetime, timezone
from typing import Any


# ── P5.9: Constants ───────────────────────────────────────────────────────────

_TRUNC_LEN: int = 12             # Hex chars to retain from HMAC digest
_KID_DEFAULT: str = "kid_dev"    # Safe default for dev/CI (not for production-required mode)
_KID_PATTERN: re.Pattern = re.compile(r"^[A-Za-z0-9._-]{1,32}$")


# ── P5.9: Kid + pepper helpers ────────────────────────────────────────────────

def _load_kid() -> str:
    """Read and validate KILL_SWITCH_AUDIT_FINGERPRINT_KID.

    Returns:
        kid string — 1–32 chars, [A-Za-z0-9._-] only, no colon.

    Raises:
        RuntimeError("INVALID_FINGERPRINT_KID"): If the value is malformed.
    """
    kid = os.getenv("KILL_SWITCH_AUDIT_FINGERPRINT_KID", _KID_DEFAULT)
    if ":" in kid:
        raise RuntimeError(
            f"INVALID_FINGERPRINT_KID: colon (':') is not allowed in kid value, "
            f"got {kid!r}. The colon is the separator between kid and hex digest."
        )
    if not _KID_PATTERN.match(kid):
        raise RuntimeError(
            f"INVALID_FINGERPRINT_KID: {kid!r} must be 1–32 chars using "
            f"[A-Za-z0-9._-] only. Check KILL_SWITCH_AUDIT_FINGERPRINT_KID."
        )
    return kid


def _load_pepper() -> bytes | None:
    """Load pepper bytes from environment variables.

    Priority order:
      1. KILL_SWITCH_AUDIT_FINGERPRINT_PEPPER_B64  (base64 — preferred for production)
      2. KILL_SWITCH_AUDIT_FINGERPRINT_PEPPER      (utf-8 string — fallback / dev)
      3. None — allowed only when REQUIRED=0 AND STRICT=0 (dev/CI)

    Returns:
        Pepper bytes, or None if not set and production-required mode is off.

    Raises:
        RuntimeError("FINGERPRINT_PEPPER_NOT_SET"): If neither env var is set
            and KILL_SWITCH_AUDIT_REQUIRED=1 or KILL_SWITCH_AUDIT_STRICT=1.
    """
    b64 = os.getenv("KILL_SWITCH_AUDIT_FINGERPRINT_PEPPER_B64", "").strip()
    if b64:
        return base64.b64decode(b64)

    plain = os.getenv("KILL_SWITCH_AUDIT_FINGERPRINT_PEPPER", "").strip()
    if plain:
        return plain.encode("utf-8")

    # Neither env var set — check if production-required context demands pepper
    required = os.getenv("KILL_SWITCH_AUDIT_REQUIRED", "0").strip() == "1"
    strict = os.getenv("KILL_SWITCH_AUDIT_STRICT", "0").strip() == "1"

    if required or strict:
        raise RuntimeError(
            "FINGERPRINT_PEPPER_NOT_SET: "
            "KILL_SWITCH_AUDIT_FINGERPRINT_PEPPER or "
            "KILL_SWITCH_AUDIT_FINGERPRINT_PEPPER_B64 must be set when "
            "KILL_SWITCH_AUDIT_REQUIRED=1 or KILL_SWITCH_AUDIT_STRICT=1. "
            "Store the pepper in AWS Secrets Manager and inject at runtime; "
            "never commit the pepper value to the repository."
        )

    # Dev/CI: no pepper configured — fingerprint will be None
    return None


def fingerprint_token(token: str | None) -> str | None:
    """Compute HMAC-SHA256(pepper, token) fingerprint with Key-ID prefix.

    Returns the rotation-ready fingerprint format: "<kid>:<hex[:TRUNC_LEN]>"

    The kid prefix identifies which pepper was used, enabling historical
    records to remain verifiable after key rotation (keep old pepper offline
    with the matching kid; issue a new kid when rotating to a new pepper).

    Args:
        token: Raw admin token string, or None/empty.

    Returns:
        "<kid>:<12 lowercase hex chars>" string, or None if:
          - token is None or empty (no value to fingerprint), OR
          - pepper is not configured and REQUIRED/STRICT mode is off (dev/CI only).

    Raises:
        RuntimeError("INVALID_FINGERPRINT_KID"): If KID env var is malformed.
        RuntimeError("FINGERPRINT_PEPPER_NOT_SET"): If pepper is absent in
            REQUIRED or STRICT mode. Callers must treat this as a fatal
            misconfiguration — kill-switch state must not be mutated.
    """
    if not token:
        return None

    kid = _load_kid()
    pepper_bytes = _load_pepper()

    if pepper_bytes is None:
        # Dev/CI mode: no pepper configured; return None to indicate unavailable fingerprint.
        # Production-required mode raises before reaching here.
        return None

    digest = hmac.new(pepper_bytes, token.encode("utf-8"), hashlib.sha256).hexdigest()
    return f"{kid}:{digest[:_TRUNC_LEN]}"


# ── P5.3 (legacy): SHA-256 fingerprint for non-token fields ───────────────────

def _fingerprint(secret: str, length: int = 12) -> str:
    """Return a short SHA-256 hex fingerprint (not HMAC — used for IP addresses only).

    IP addresses are not secret credentials and do not require HMAC protection.
    Admin tokens use fingerprint_token() which applies HMAC with a secret pepper.
    """
    return hashlib.sha256(secret.encode("utf-8")).hexdigest()[:length]


# ── P6.1: Boot-time fingerprint config validation ─────────────────────────────

def validate_kill_switch_audit_fingerprint_config() -> None:
    """Validate kid + pepper configuration at boot time (Fail-closed).

    Intended to be called from startup_event() when KILL_SWITCH_AUDIT_REQUIRED=1
    or KILL_SWITCH_AUDIT_STRICT=1. If either constraint is active and the pepper
    or kid is misconfigured, this raises immediately so the pod fails to start
    before becoming READY (CrashLoop → operator is alerted).

    Never logs the pepper or kid value — only the error code.

    Raises:
        RuntimeError("INVALID_FINGERPRINT_KID"): Kid env var has illegal chars or colon.
        RuntimeError("FINGERPRINT_PEPPER_NOT_SET"): Pepper absent in REQUIRED/STRICT mode.
        Exception: base64.b64decode failure if PEPPER_B64 is malformed.
    """
    _load_kid()      # validates KID format; raises on invalid
    _load_pepper()   # validates pepper presence; raises if missing in required/strict mode


# ── Audit record builder ───────────────────────────────────────────────────────

def build_kill_switch_audit_record(
    *,
    request_id: str | None,
    actor_token: str,
    actor_ip: str,
    mode_from: str,
    mode_to: str,
    reason: str,
    ttl_minutes: int,
    result: str,
    error: str | None = None,
) -> dict[str, Any]:
    """Build a structured audit record for a kill-switch change attempt.

    The record never contains raw token values or raw IP addresses;
    only short fingerprints are stored.

    P5.9: actor.token_fingerprint is now "<kid>:<HMAC-SHA256[:12]>" — a
    rotation-ready HMAC fingerprint. The kid prefix identifies which pepper
    version was used, enabling historical verification after key rotation.

    Args:
        request_id:  X-Request-ID from the incoming request (may be None).
        actor_token: Raw admin token (HMAC-fingerprinted before storage; never stored raw).
        actor_ip:    Client IP address (SHA-256 hashed before storage; never stored raw).
        mode_from:   Previous kill-switch mode value.
        mode_to:     Requested kill-switch mode value.
        reason:      Operator-supplied reason (max 200 chars, validated by Pydantic upstream).
        ttl_minutes: Requested TTL (0 = permanent).
        result:      "ok" if state was successfully changed, "failed" otherwise.
        error:       Error description if result == "failed", else None.

    Returns:
        Audit record dict suitable for JSON serialisation.

    Raises:
        RuntimeError: If fingerprint_token() fails due to misconfiguration
            (e.g., FINGERPRINT_PEPPER_NOT_SET in REQUIRED/STRICT mode).
            Callers (admin router step 4) must catch this and return HTTP 500
            without mutating kill-switch state.
    """
    return {
        "schema_version": "1.0",
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "request_id": request_id,
        "actor": {
            # P5.9: HMAC+kid fingerprint (rotation-ready). kid identifies pepper version.
            "token_fingerprint": fingerprint_token(actor_token),
            # P5.3: SHA-256 hash of IP (not a secret credential; no HMAC needed).
            "ip_hash": _fingerprint(actor_ip),
        },
        "change": {
            "mode_from": mode_from,
            "mode_to": mode_to,
            "reason": reason,
            "ttl_minutes": ttl_minutes,
        },
        "result": result,
        "error": error,
    }
