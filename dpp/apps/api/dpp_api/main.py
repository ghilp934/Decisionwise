"""DPP API - FastAPI Application Entry Point."""

import json
import logging
import os
import uuid
from pathlib import Path

from fastapi import FastAPI, Request, status
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse, FileResponse
from fastapi.staticfiles import StaticFiles
from starlette.exceptions import HTTPException as StarletteHTTPException

from dpp_api.context import request_id_var
from dpp_api.enforce import PlanViolationError
from dpp_api.routers import health, runs, usage
from dpp_api.schemas import ProblemDetail
from dpp_api.utils import configure_json_logging

app = FastAPI(
    title="Decisionwise API",
    description="Agent-centric decision execution platform with idempotent metering, RFC 9457 error handling, and IETF RateLimit headers.",
    version="0.4.2.2",
    docs_url="/api-docs",  # MTS-3: Moved to /api-docs to free /docs for documentation
    redoc_url="/redoc",
    openapi_version="3.1.0",  # MTS-3: Locked to OpenAPI 3.1.0
)

# P1-9: Configure structured JSON logging
# Set DPP_JSON_LOGS=false to disable (defaults to true for production)
if os.getenv("DPP_JSON_LOGS", "true").lower() != "false":
    configure_json_logging(log_level=os.getenv("LOG_LEVEL", "INFO"))
    logger = logging.getLogger(__name__)
    logger.info("Structured JSON logging enabled")

# P1-G: CORS middleware with browser-compatible security
# MDN: credentials mode CANNOT use wildcard origins
cors_origins_env = os.getenv("CORS_ALLOWED_ORIGINS", "")
if cors_origins_env:
    # Production: explicit allowlist (comma-separated)
    allowed_origins = [origin.strip() for origin in cors_origins_env.split(",") if origin.strip()]
else:
    # Dev fallback: localhost variants (safe default)
    allowed_origins = [
        "http://localhost:3000",
        "http://localhost:8000",
        "http://127.0.0.1:3000",
        "http://127.0.0.1:8000",
    ]

app.add_middleware(
    CORSMiddleware,
    allow_origins=allowed_origins,  # P1-G: Never "*" with credentials
    allow_credentials=True,
    allow_methods=["GET", "POST", "PUT", "DELETE", "OPTIONS"],  # Explicit methods
    allow_headers=["Authorization", "Content-Type", "Idempotency-Key"],  # Explicit headers
    expose_headers=["X-DPP-Cost-Reserved", "X-DPP-Cost-Actual", "X-DPP-Cost-Minimum-Fee"],  # P1-6
)


# ============================================================================
# P1-9: Request ID Middleware
# ============================================================================


@app.middleware("http")
async def request_id_middleware(request: Request, call_next):
    """Generate and propagate request_id for observability.

    P1-9: Each request gets a unique request_id (UUID v4).
    - Accepts X-Request-ID header from client (optional)
    - Generates new UUID if not provided
    - Sets context variable for logging
    - Returns X-Request-ID in response headers
    """
    # Get or generate request_id
    request_id = request.headers.get("X-Request-ID") or str(uuid.uuid4())

    # Set context variable for logging
    request_id_var.set(request_id)

    # Process request
    response = await call_next(request)

    # Add request_id to response headers
    response.headers["X-Request-ID"] = request_id

    return response


# ============================================================================
# RFC 9457 Global Exception Handlers
# ============================================================================


@app.exception_handler(PlanViolationError)
async def plan_violation_handler(request: Request, exc: PlanViolationError) -> JSONResponse:
    """Handle plan violation errors with RFC 9457 Problem Details format.

    Returns application/problem+json with plan-specific error details.
    P1-2: Includes Retry-After header for 429 responses using exc.retry_after field.
    """
    problem = ProblemDetail(
        type=exc.error_type,
        title=exc.title,
        status=exc.status_code,
        detail=exc.detail,
        instance=request.url.path,
    )

    headers = {}
    # P1-2: Add Retry-After header using retry_after field (no regex parsing)
    if exc.status_code == 429 and exc.retry_after is not None:
        headers["Retry-After"] = str(exc.retry_after)

    return JSONResponse(
        status_code=exc.status_code,
        content=problem.model_dump(exclude_none=True),
        media_type="application/problem+json",
        headers=headers,
    )


@app.exception_handler(StarletteHTTPException)
async def http_exception_handler(request: Request, exc: StarletteHTTPException) -> JSONResponse:
    """Handle HTTP exceptions with RFC 9457 Problem Details format.

    Returns application/problem+json with top-level RFC 9457 fields.
    No {"detail": ...} wrapper.

    P0-1: Preserves dict detail fields for structured error responses (RFC 9457 compliant).
    """
    # P0-1: Don't force-cast detail to str - preserve dict if provided
    detail_value = exc.detail if exc.detail is not None else _get_title_for_status(exc.status_code)

    problem = ProblemDetail(
        type=f"https://dpp.example.com/problems/http-{exc.status_code}",
        title=_get_title_for_status(exc.status_code),
        status=exc.status_code,
        detail=detail_value,
        instance=request.url.path,
    )

    return JSONResponse(
        status_code=exc.status_code,
        content=problem.model_dump(exclude_none=True),
        media_type="application/problem+json",
    )


@app.exception_handler(RequestValidationError)
async def validation_exception_handler(request: Request, exc: RequestValidationError) -> JSONResponse:
    """Handle request validation errors with RFC 9457 Problem Details format.

    Returns 400 Bad Request with application/problem+json.
    """
    # Extract first error for detail message
    first_error = exc.errors()[0] if exc.errors() else {}
    field = ".".join(str(loc) for loc in first_error.get("loc", []))
    msg = first_error.get("msg", "Validation error")

    problem = ProblemDetail(
        type="https://dpp.example.com/problems/validation-error",
        title="Request Validation Failed",
        status=status.HTTP_400_BAD_REQUEST,
        detail=f"Invalid field '{field}': {msg}",
        instance=request.url.path,
    )

    return JSONResponse(
        status_code=status.HTTP_400_BAD_REQUEST,
        content=problem.model_dump(exclude_none=True),
        media_type="application/problem+json",
    )


@app.exception_handler(Exception)
async def general_exception_handler(request: Request, exc: Exception) -> JSONResponse:
    """Handle uncaught exceptions with RFC 9457 Problem Details format.

    Returns 500 Internal Server Error with application/problem+json.
    """
    problem = ProblemDetail(
        type="https://dpp.example.com/problems/internal-error",
        title="Internal Server Error",
        status=status.HTTP_500_INTERNAL_SERVER_ERROR,
        detail="An unexpected error occurred. Please try again later.",
        instance=request.url.path,
    )

    # Log the actual exception for debugging (TODO: add structured logging)
    import logging
    logger = logging.getLogger(__name__)
    logger.error(f"Unhandled exception: {exc}", exc_info=True)

    return JSONResponse(
        status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
        content=problem.model_dump(exclude_none=True),
        media_type="application/problem+json",
    )


def _get_title_for_status(status_code: int) -> str:
    """Get human-readable title for HTTP status code."""
    titles = {
        400: "Bad Request",
        401: "Unauthorized",
        402: "Payment Required",
        403: "Forbidden",
        404: "Not Found",
        409: "Conflict",
        429: "Too Many Requests",
        500: "Internal Server Error",
        502: "Bad Gateway",
        503: "Service Unavailable",
    }
    return titles.get(status_code, f"HTTP {status_code}")


# Include routers
app.include_router(health.router, tags=["health"])
app.include_router(runs.router)  # API-01: Runs endpoints
app.include_router(usage.router)  # STEP D: Usage analytics


# ============================================================================
# MTS-3: AI-Friendly Documentation Endpoints
# ============================================================================


@app.get("/.well-known/openapi.json")
async def well_known_openapi():
    """
    OpenAPI 3.1.0 specification endpoint.

    MTS-3.0-DOC: Provides machine-readable API specification at well-known location.
    Returns: OpenAPI 3.1.0 JSON schema
    """
    return JSONResponse(content=app.openapi())


@app.get("/pricing/ssot.json")
async def pricing_ssot():
    """
    Canonical Pricing Single Source of Truth (SSoT).

    MTS-3.0-DOC: Provides machine-readable pricing configuration.
    Returns: Pricing SSoT v0.2.1 JSON
    """
    # Load SSoT from canonical file
    ssot_path = Path(__file__).parent / "pricing" / "fixtures" / "pricing_ssot.json"

    try:
        with open(ssot_path, "r", encoding="utf-8") as f:
            ssot_data = json.load(f)
        return JSONResponse(content=ssot_data)
    except FileNotFoundError:
        # Return 500 with ProblemDetails if SSoT file is missing
        problem = ProblemDetail(
            type="https://iana.org/assignments/http-problem-types#internal-error",
            title="Pricing SSoT Not Found",
            status=500,
            detail="Pricing configuration file not found. Contact support.",
        )
        return JSONResponse(
            status_code=500,
            content=problem.model_dump(exclude_none=True),
            media_type="application/problem+json",
        )
    except json.JSONDecodeError:
        # Return 500 with ProblemDetails if SSoT file is malformed
        problem = ProblemDetail(
            type="https://iana.org/assignments/http-problem-types#internal-error",
            title="Pricing SSoT Parse Error",
            status=500,
            detail="Pricing configuration file is malformed. Contact support.",
        )
        return JSONResponse(
            status_code=500,
            content=problem.model_dump(exclude_none=True),
            media_type="application/problem+json",
        )


@app.get("/")
async def root() -> dict[str, str]:
    """Root endpoint."""
    return {
        "service": "Decisionwise API",
        "version": "0.4.2.2",
        "status": "running",
        "docs": "/llms.txt",
    }


# ============================================================================
# MTS-3: Static File Serving (llms.txt, docs)
# ============================================================================

# Mount static files last (after all routes)
# This serves /public directory at root path
public_dir = Path(__file__).parent.parent.parent.parent / "public"
if public_dir.exists():
    app.mount("/", StaticFiles(directory=str(public_dir), html=True), name="static")
