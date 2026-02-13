"""Request context management for observability.

P1-9: Context variables for request tracking across async boundaries.
"""

from contextvars import ContextVar

# Request ID - unique per HTTP request
request_id_var: ContextVar[str] = ContextVar("request_id", default="")
