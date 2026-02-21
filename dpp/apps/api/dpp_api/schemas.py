"""Pydantic schemas for API requests/responses."""

from datetime import datetime
from typing import Any, Optional

from pydantic import BaseModel, Field


# ============================================================================
# POST /v1/runs - Request/Response
# ============================================================================


class RunReservation(BaseModel):
    """Reservation parameters for run submission."""

    max_cost_usd: str = Field(
        ..., description="Maximum cost in USD (4dp string)", pattern=r"^\d+(\.\d{1,4})?$"
    )
    timebox_sec: int = Field(default=90, ge=1, le=90, description="Execution timeout")
    min_reliability_score: float = Field(
        default=0.8, ge=0.0, le=1.0, description="Minimum reliability score"
    )


class RunMeta(BaseModel):
    """Metadata for run."""

    trace_id: Optional[str] = None
    profile_version: str = "v0.4.2.2"


class RunCreateRequest(BaseModel):
    """Request body for POST /v1/runs."""

    pack_type: str = Field(..., description="Pack type (decision, url, ocr, etc.)")
    inputs: dict[str, Any] = Field(..., description="Pack-specific inputs")
    reservation: RunReservation
    meta: Optional[RunMeta] = None


class PollInfo(BaseModel):
    """Polling information."""

    href: str
    recommended_interval_ms: int = 1500
    max_wait_sec: int = 90


class RunReceipt(BaseModel):
    """Response for POST /v1/runs (202 Accepted)."""

    run_id: str
    status: str
    poll: PollInfo
    reservation: dict[str, str]
    meta: dict[str, Any]


# ============================================================================
# GET /v1/runs/{run_id} - Response
# ============================================================================


class CostInfo(BaseModel):
    """Cost information."""

    reserved_usd: str
    used_usd: str
    minimum_fee_usd: str
    budget_remaining_usd: str


class ResultInfo(BaseModel):
    """Result information for completed runs."""

    presigned_url: Optional[str] = None
    sha256: Optional[str] = None
    expires_at: Optional[datetime] = None


class ErrorInfo(BaseModel):
    """Error information for failed runs."""

    reason_code: str
    detail: str


class RunStatusResponse(BaseModel):
    """Response for GET /v1/runs/{run_id}."""

    run_id: str
    status: str
    money_state: str
    cost: CostInfo
    result: Optional[ResultInfo] = None
    error: Optional[ErrorInfo] = None
    meta: dict[str, Any]


# ============================================================================
# RFC 9457 Problem Details (DEC-4213)
# ============================================================================


class ProblemDetail(BaseModel):
    """RFC 9457 Problem Details for HTTP API errors.

    Used for plan enforcement violations and other API errors.

    RFC 9457: detail can be either a string or a structured object (dict).
    """

    type: str = Field(..., description="URI reference identifying the problem type")
    title: str = Field(..., description="Short, human-readable summary")
    status: int = Field(..., description="HTTP status code")
    detail: str | dict[str, Any] = Field(..., description="Human-readable explanation or structured error details")
    instance: Optional[str] = Field(None, description="URI reference identifying the specific occurrence")


# ============================================================================
# GET /v1/tenants/{tenant_id}/usage - Response
# ============================================================================


class UsageDailySummary(BaseModel):
    """Daily usage summary for a tenant."""

    usage_date: str = Field(..., description="Date in YYYY-MM-DD format")
    runs_count: int
    success_count: int
    fail_count: int
    cost_usd_micros_sum: int
    reserved_usd_micros_sum: int


class UsageResponse(BaseModel):
    """Response for GET /v1/tenants/{tenant_id}/usage."""

    tenant_id: str
    from_date: str = Field(..., description="Start date (inclusive) in YYYY-MM-DD")
    to_date: str = Field(..., description="End date (inclusive) in YYYY-MM-DD")
    daily_usage: list[UsageDailySummary]


# ============================================================================
# Phase 2: Auth/Email Onboarding - Request/Response
# ============================================================================


class SignupRequest(BaseModel):
    """Request body for POST /v1/auth/signup."""

    email: str = Field(
        ...,
        description="User email address",
        pattern=r"^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$",
    )
    password: str = Field(
        ...,
        description="User password (minimum 8 characters)",
        min_length=8,
    )


class LoginRequest(BaseModel):
    """Request body for POST /v1/auth/login."""

    email: str = Field(
        ...,
        description="User email address",
        pattern=r"^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$",
    )
    password: str = Field(..., description="User password", min_length=8)


class AuthResponse(BaseModel):
    """Response for successful auth operations."""

    user_id: str = Field(..., description="Supabase user UUID")
    email: str = Field(..., description="User email")
    email_confirmed: bool = Field(..., description="Email confirmation status")
    access_token: Optional[str] = Field(
        None, description="JWT access token (only for login)"
    )
    refresh_token: Optional[str] = Field(
        None, description="JWT refresh token (only for login)"
    )
    message: Optional[str] = Field(
        None, description="Additional message (e.g., 'Check your email')"
    )


# ============================================================================
# P0-3: Token Management - Request/Response
# ============================================================================


class TokenCreateRequest(BaseModel):
    """Request body for POST /v1/tokens."""

    name: str = Field(..., description="Human-readable token name", min_length=1, max_length=255)
    scopes: Optional[list[str]] = Field(None, description="Token scopes (future use)")
    expires_in_days: Optional[int] = Field(
        None, ge=1, le=365, description="Token expiration in days (null = never)"
    )


class TokenCreateResponse(BaseModel):
    """Response for POST /v1/tokens (display-once)."""

    token: str = Field(..., description="Raw token (display ONCE, never stored)")
    token_id: str = Field(..., description="Token UUID")
    prefix: str = Field(..., description="Token prefix (dp_live, dp_test)")
    last4: str = Field(..., description="Last 4 characters for display")
    name: str = Field(..., description="Token name")
    scopes: list[str] = Field(default_factory=list, description="Token scopes")
    status: str = Field(..., description="Token status (active)")
    created_at: datetime = Field(..., description="Creation timestamp")
    expires_at: Optional[datetime] = Field(None, description="Expiration timestamp")


class TokenListItem(BaseModel):
    """Token list item (no raw token)."""

    token_id: str = Field(..., description="Token UUID")
    name: str = Field(..., description="Token name")
    prefix: str = Field(..., description="Token prefix")
    last4: str = Field(..., description="Last 4 characters")
    scopes: list[str] = Field(default_factory=list, description="Token scopes")
    status: str = Field(..., description="active | rotating | revoked | expired")
    created_at: datetime = Field(..., description="Creation timestamp")
    expires_at: Optional[datetime] = Field(None, description="Expiration timestamp")
    revoked_at: Optional[datetime] = Field(None, description="Revocation timestamp")
    last_used_at: Optional[datetime] = Field(None, description="Last usage timestamp")


class TokenListResponse(BaseModel):
    """Response for GET /v1/tokens."""

    tokens: list[TokenListItem] = Field(..., description="List of tokens")


class TokenRevokeResponse(BaseModel):
    """Response for POST /v1/tokens/{token_id}/revoke."""

    token_id: str = Field(..., description="Revoked token UUID")
    status: str = Field(..., description="New status (revoked)")
    revoked_at: datetime = Field(..., description="Revocation timestamp")


class TokenRotateResponse(BaseModel):
    """Response for POST /v1/tokens/{token_id}/rotate."""

    new_token: str = Field(..., description="New raw token (display ONCE)")
    new_token_id: str = Field(..., description="New token UUID")
    old_token_id: str = Field(..., description="Old token UUID")
    old_status: str = Field(..., description="Old token status (rotating)")
    old_expires_at: datetime = Field(..., description="Old token grace period expiration")
    grace_period_minutes: int = Field(..., description="Grace period in minutes")


class TokenRevokeAllResponse(BaseModel):
    """Response for POST /v1/tokens/revoke-all."""

    revoked_count: int = Field(..., description="Number of tokens revoked")
    revoked_token_ids: list[str] = Field(..., description="List of revoked token UUIDs")
