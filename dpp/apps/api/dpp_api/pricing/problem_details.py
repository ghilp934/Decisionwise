"""
RFC 9457 Problem Details for HTTP APIs
"""

from pydantic import BaseModel, Field, ConfigDict
from typing import List, Optional
from fastapi.responses import JSONResponse


class ViolatedPolicy(BaseModel):
    """Violated policy details (RFC 9457 extension)"""
    policy: str  # No alias - JSON field name is "policy"
    limit: int
    current: int
    window_seconds: Optional[int] = None


class ProblemDetails(BaseModel):
    """
    RFC 9457 Problem Details model
    
    Standard fields:
    - type: URI reference identifying the problem type
    - title: Short, human-readable summary
    - status: HTTP status code
    - detail: Human-readable explanation
    - instance: URI reference identifying the specific occurrence
    
    Extension fields:
    - violated_policies: List of violated policies (Decisionwise extension)
    """
    type: str
    title: str
    status: int
    detail: Optional[str] = None
    instance: Optional[str] = None
    violated_policies: List[ViolatedPolicy] = Field(
        default_factory=list,
        alias="violated-policies"
    )

    model_config = ConfigDict(
        populate_by_name=True,
        json_schema_extra={
            "example": {
                "type": "https://iana.org/assignments/http-problem-types#quota-exceeded",
                "title": "Request cannot be satisfied as assigned quota has been exceeded",
                "status": 429,
                "detail": "RPM limit of 600 requests per minute exceeded",
                "violated-policies": [
                    {
                        "policy_name": "rpm",
                        "limit": 600,
                        "current": 601,
                        "window_seconds": 60
                    }
                ]
            }
        }
    )


def create_problem_details_response(
    *,
    type_uri: str,
    title: str,
    status: int,
    detail: Optional[str] = None,
    instance: Optional[str] = None,
    violated_policies: Optional[List[ViolatedPolicy]] = None,
    headers: Optional[dict[str, str]] = None
) -> JSONResponse:
    """
    Create RFC 9457 Problem Details JSON response

    P0-5: Direct constructor API for test compatibility

    Args:
        type_uri: URI reference identifying the problem type
        title: Short, human-readable summary
        status: HTTP status code
        detail: Human-readable explanation
        instance: URI reference identifying the specific occurrence
        violated_policies: List of violated policies (extension)
        headers: Optional additional headers

    Returns:
        JSONResponse with application/problem+json content type
    """
    # Build ProblemDetails instance
    problem = ProblemDetails(
        type=type_uri,
        title=title,
        status=status,
        detail=detail,
        instance=instance,
        violated_policies=violated_policies or []
    )

    response_headers = {"Content-Type": "application/problem+json"}
    if headers:
        response_headers.update(headers)

    # Serialize with alias (violated-policies instead of violated_policies)
    content = problem.model_dump(by_alias=True, exclude_none=True)

    return JSONResponse(
        status_code=problem.status,
        content=content,
        headers=response_headers
    )
